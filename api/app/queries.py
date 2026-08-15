"""Every SQL statement the API runs, one function per endpoint need."""

from __future__ import annotations

import json
import logging
import sqlite3

from metrics.timeline import build_timeline

log = logging.getLogger("api")


PLAYER_SORTS = {
    "pir_avg": "pir_avg",
    "pir_total": "pir_total",
    "pir_per36": "pir_per36",
    "pm_total": "pm_total",
    "pm_per36": "pm_per36",
    "points": "points",
    "clutch_pm": "clutch_pm",
    "clutch_points": "clutch_points",
    "fouls_drawn_per100": "fouls_drawn_per100",
}

TEAM_SORTS = {
    "possessions_avg": "possessions_avg",
    "fouls_drawn_per100": "fouls_drawn_per100",
    "max_run": "max_run",
    "max_blown_lead": "max_blown_lead",
    "clutch_pts_for": "clutch_pts_for",
}


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


SECONDS_PER_36 = 2160.0
RADAR_MIN_GAMES = 5

PLAYER_RADAR = [
    ("pts", "PTS", "pts36", False),
    ("fg3_pct", "3PT%", "fg3_pct", False),
    ("ts_pct", "TS%", "ts_pct", False),
    ("ast", "AST", "ast36", False),
    ("oreb", "OREB", "oreb36", False),
    ("dreb", "DREB", "dreb36", False),
    ("stl", "STL", "stl36", False),
    ("blk", "BLK", "blk36", False),
    ("fouls_drawn", "Fouls Drawn", "fd36", False),
    ("ball_security", "Ball Security", "tov100", True),
    ("opp_fg_pct", "Opp FG%", "opp_fg_pct", True),
    ("drtg", "DRTG", "drtg", True),
]

TEAM_RADAR = [
    ("ortg", "ORTG", "ortg", False),
    ("efg", "eFG%", "efg_pct", False),
    ("oreb", "OREB%", "oreb_pct", False),
    ("fouls_drawn", "Fouls /100", "fouls_drawn_per100", False),
    ("tov", "Ball Security", "tov100", True),
    ("dreb", "DREB%", "dreb_pct", False),
    ("opp_efg", "Opp eFG%", "opp_efg_pct", True),
    ("drtg", "DRTG", "drtg", True),
]


def _percentile(values: list[float], target: float) -> float:
    """Share of the field this value beats, 0-100."""
    if not values:
        return 0.0
    below = sum(1 for v in values if v < target)
    equal = sum(1 for v in values if v == target)
    return round(100.0 * (below + 0.5 * equal) / len(values), 1)


def _radar(field: list[dict], subject: dict, axes) -> list[dict]:
    """Percentile-rank the subject against the field on each axis."""
    out = []
    for key, label, metric, lower_is_better in axes:
        value = subject.get(metric)
        if value is None:
            continue
        peers = [r[metric] for r in field if r.get(metric) is not None]
        pct = _percentile(peers, float(value))
        if lower_is_better:
            pct = round(100.0 - pct, 1)
        out.append({
            "key": key,
            "label": label,
            "value": round(float(value), 2),
            "percentile": pct,
            "lower_is_better": lower_is_better,
        })
    return out


MIN_FG3A = 20
MIN_OPP_FGA = 100


def _derived(row: dict) -> dict:
    """The twelve radar metrics, from the stored sums."""
    secs = row.get("seconds") or 0
    poss = row.get("poss_share") or 0

    def per36(column: str) -> float | None:
        return None if not secs else (row.get(column) or 0) * SECONDS_PER_36 / secs

    def per100(column: str) -> float | None:
        return None if not poss else 100.0 * (row.get(column) or 0) / poss

    fg3a = row.get("fg3a") or 0
    fga = (row.get("fg2a") or 0) + fg3a
    fta = row.get("fta") or 0
    ts_attempts = fga + 0.44 * fta
    opp_fga = row.get("opp_fga") or 0

    return {
        "pts36": per36("points"),
        "fg3_pct": (100.0 * (row.get("fg3m") or 0) / fg3a) if fg3a >= MIN_FG3A else None,
        "ts_pct": (100.0 * (row.get("points") or 0) / (2 * ts_attempts)) if ts_attempts else None,
        "ast36": per36("assists"),
        "oreb36": per36("reb_off"),
        "dreb36": per36("reb_def"),
        "stl36": per36("steals"),
        "blk36": per36("blocks_favour"),
        "fd36": per36("fouls_drawn"),
        "tov100": per100("turnovers"),
        "opp_fg_pct": (100.0 * (row.get("opp_fgm") or 0) / opp_fga) if opp_fga >= MIN_OPP_FGA else None,
        "drtg": per100("opp_points") if (row.get("opp_points") is not None and poss) else None,
    }


def _derived_team(row: dict) -> dict:
    """Team rates: ratings, shooting and rebounding."""
    poss = row.get("possessions") or 0
    opp_poss = row.get("opp_possessions") or 0

    def shooting(prefix: str) -> tuple[float | None, float | None]:
        p = f"{prefix}_" if prefix else ""
        fg2m, fg3m = row.get(f"{p}fg2m") or 0, row.get(f"{p}fg3m") or 0
        fga = (row.get(f"{p}fg2a") or 0) + (row.get(f"{p}fg3a") or 0)
        fta = row.get(f"{p}fta") or 0
        pts = row.get(f"{p}points") or 0
        efg = (100.0 * (fg2m + fg3m + 0.5 * fg3m) / fga) if fga else None
        attempts = fga + 0.44 * fta
        ts = (100.0 * pts / (2 * attempts)) if attempts else None
        return efg, ts

    efg, ts = shooting("")
    opp_efg, _ = shooting("opp")

    oreb, dreb = row.get("reb_off") or 0, row.get("reb_def") or 0
    opp_oreb, opp_dreb = row.get("opp_reb_off") or 0, row.get("opp_reb_def") or 0
    ortg = (100.0 * (row.get("points") or 0) / poss) if poss else None
    drtg = (100.0 * (row.get("opp_points") or 0) / opp_poss) if opp_poss else None

    return {
        "ortg": ortg,
        "drtg": drtg,
        "net_rtg": (ortg - drtg) if (ortg is not None and drtg is not None) else None,
        "efg_pct": efg,
        "ts_pct": ts,
        "opp_efg_pct": opp_efg,
        "oreb_pct": (100.0 * oreb / (oreb + opp_dreb)) if (oreb + opp_dreb) else None,
        "dreb_pct": (100.0 * dreb / (dreb + opp_oreb)) if (dreb + opp_oreb) else None,
        "tov100": (100.0 * (row.get("turnovers") or 0) / poss) if poss else None,
        "opp_tov100": (100.0 * (row.get("opp_turnovers") or 0) / opp_poss) if opp_poss else None,
        "ast100": (100.0 * (row.get("assists") or 0) / poss) if poss else None,
        "stl100": (100.0 * (row.get("steals") or 0) / opp_poss) if opp_poss else None,
        "blk100": (100.0 * (row.get("blocks_favour") or 0) / opp_poss) if opp_poss else None,
    }


def _radar_columns_missing(exc: sqlite3.OperationalError) -> bool:
    return "no such column" in str(exc)


def player_radar(conn, source: str, season_code: str, player: dict) -> list[dict]:
    """Twelve rate metrics, ranked against everyone who has played enough for a rate to mean anything."""
    if not (player.get("seconds") or 0) or (player.get("games_played") or 0) < RADAR_MIN_GAMES:
        return []

    try:
        rows = _rows(conn.execute(
            """SELECT points, reb_off, reb_def, assists, steals, blocks_favour,
                      turnovers, fouls_drawn, fg2a, fg3m, fg3a, fta, seconds,
                      poss_share, opp_fgm, opp_fga, opp_points
               FROM player_season_metrics
               WHERE source=? AND season_code=? AND games_played >= ? AND seconds > 0""",
            (source, season_code, RADAR_MIN_GAMES),
        ))
    except sqlite3.OperationalError as exc:
        if _radar_columns_missing(exc):
            log.warning("radar unavailable for %s: %s — run `python -m metrics`",
                        season_code, exc)
            return []
        raise

    field = [_derived(r) for r in rows]
    return _radar(field, _derived(player), PLAYER_RADAR)


def team_radar(conn, source: str, season_code: str, team: dict) -> list[dict]:
    """Season rates for the club, ranked against the rest of the league."""
    try:
        field = [
            {**r, **_derived_team(r)}
            for r in _rows(conn.execute(
                """SELECT t.*, s.point_diff
                   FROM team_season_metrics t
                   LEFT JOIN standings s ON s.source=t.source AND s.season_code=t.season_code
                                        AND s.club_code=t.club_code
                   WHERE t.source=? AND t.season_code=?""",
                (source, season_code),
            ))
        ]
    except sqlite3.OperationalError as exc:
        if _radar_columns_missing(exc):
            log.warning("team radar unavailable for %s: %s", season_code, exc)
            return []
        raise
    return _radar(field, team, TEAM_RADAR)


def latest_season(conn, source: str) -> str | None:
    """Newest season that has final games — same rule as the metrics CLI."""
    row = conn.execute(
        """SELECT g.season_code FROM games g
           JOIN seasons s ON s.source = g.source AND s.code = g.season_code
           WHERE g.source = ? AND g.is_final = 1
           GROUP BY g.season_code ORDER BY s.year DESC LIMIT 1""",
        (source,),
    ).fetchone()
    return row["season_code"] if row else None


def seasons_version(conn, source: str) -> str:
    """Cache version for the season *list*."""
    row = conn.execute(
        """SELECT COUNT(*) AS n, MAX(value) AS newest FROM metrics_meta
           WHERE key LIKE ?""",
        (f"computed_at:{source}:%",),
    ).fetchone()
    return f"{row['n']}:{row['newest']}" if row else "empty"


def list_seasons(conn, source: str) -> list[dict]:
    """Seasons with final games."""
    return _rows(conn.execute(
        """SELECT g.season_code, s.name AS season_name, s.year,
                  s.winner_club_code,
                  COUNT(*) AS games,
                  SUM(g.pbp_status = 'ok') AS games_with_pbp,
                  (SELECT value FROM metrics_meta
                    WHERE key = 'computed_at:' || g.source || ':' || g.season_code)
                    AS computed_at
           FROM games g
           JOIN seasons s ON s.source = g.source AND s.code = g.season_code
           WHERE g.source = ? AND g.is_final = 1
           GROUP BY g.season_code ORDER BY s.year DESC""",
        (source,),
    ))


def season_exists(conn, source: str, season_code: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM games WHERE source=? AND season_code=? AND is_final=1 LIMIT 1",
        (source, season_code),
    ).fetchone() is not None


def clubs(conn, source: str, season_code: str) -> list[dict]:
    """Club registry for a season — the crest lookup the UI resolves by code, so no other endpoint has to carry an image URL on every row."""
    return _rows(conn.execute(
        """SELECT club_code, club_name, crest_url FROM clubs
           WHERE source=? AND season_code=? ORDER BY club_code""",
        (source, season_code),
    ))


def standings(conn, source: str, season_code: str) -> list[dict]:
    return _rows(conn.execute(
        """SELECT club_code, club_name, games, wins, losses,
                  points_for, points_against, point_diff, rank
           FROM standings WHERE source=? AND season_code=? ORDER BY rank""",
        (source, season_code),
    ))


GAME_COLUMNS = """game_code, round, round_name, phase_type_code, utc_date, played,
                  home_club_code, home_club_name, home_score,
                  away_club_code, away_club_name, away_score,
                  winner_club_code, pbp_status"""


PHASES = {"RS": "Regular season", "PI": "Play-in", "PO": "Playoffs", "FF": "Final Four"}


def games(conn, source: str, season_code: str, *, round_: int | None = None,
          club: str | None = None, phase: str | None = None,
          limit: int = 50, offset: int = 0) -> list[dict]:
    where = ["source=?", "season_code=?", "is_final=1"]
    params: list = [source, season_code]
    if round_ is not None:
        where.append("round=?")
        params.append(round_)
    if phase:
        where.append("phase_type_code=?")
        params.append(phase)
    if club:
        where.append("(home_club_code=? OR away_club_code=?)")
        params += [club, club]
    params += [limit, offset]
    return _rows(conn.execute(
        f"""SELECT {GAME_COLUMNS} FROM games WHERE {' AND '.join(where)}
            ORDER BY game_code LIMIT ? OFFSET ?""",
        params,
    ))


def game(conn, source: str, season_code: str, game_code: int) -> dict | None:
    row = conn.execute(
        f"SELECT {GAME_COLUMNS}, home_partials, away_partials, audience"
        " FROM games WHERE source=? AND season_code=? AND game_code=?",
        (source, season_code, game_code),
    ).fetchone()
    if row is None:
        return None
    detail = dict(row)
    for side in ("home_partials", "away_partials"):
        try:
            detail[side] = json.loads(detail[side]) if detail[side] else None
        except (ValueError, TypeError):
            detail[side] = None
    detail["boxscore"] = _rows(conn.execute(
        """SELECT is_home, entry_type, player_code, club_code, player_name, dorsal,
                  start_five, seconds_played, points, fg2m, fg2a, fg3m, fg3a,
                  ftm, fta, reb_off, reb_def, reb_total, assists, steals, turnovers,
                  blocks_favour, blocks_against, fouls_committed, fouls_received
           FROM boxscore_lines
           WHERE source=? AND season_code=? AND game_code=?
           ORDER BY is_home DESC, entry_type, player_name""",
        (source, season_code, game_code),
    ))
    detail["player_metrics"] = _rows(conn.execute(
        """SELECT player_code, club_code, is_home, pir, pm_computed, seconds_computed,
                  fouls_drawn, clutch_seconds, clutch_points, clutch_pm
           FROM player_game_metrics
           WHERE source=? AND season_code=? AND game_code=? ORDER BY pir DESC""",
        (source, season_code, game_code),
    ))
    detail["team_metrics"] = _rows(conn.execute(
        """SELECT club_code, is_home, points, possessions, fouls_drawn, max_run,
                  max_run_detail, max_lead, lost, clutch_pts_for, clutch_pts_against,
                  clutch_pm, clutch_seconds
           FROM team_game_metrics
           WHERE source=? AND season_code=? AND game_code=? ORDER BY is_home DESC""",
        (source, season_code, game_code),
    ))
    for t in detail["team_metrics"]:
        try:
            t["max_run_detail"] = json.loads(t["max_run_detail"]) if t["max_run_detail"] else None
        except (ValueError, TypeError):
            t["max_run_detail"] = None
    return detail


def game_timeline(conn, source: str, season_code: str, game_code: int) -> dict | None:
    """Score worm — the one thing computed per request rather than stored."""
    g = conn.execute(
        """SELECT home_club_code, away_club_code, home_score, away_score, pbp_status
           FROM games WHERE source=? AND season_code=? AND game_code=?""",
        (source, season_code, game_code),
    ).fetchone()
    if g is None:
        return None
    if g["pbp_status"] != "ok":
        return {"game_code": game_code, "has_pbp": False, "points": [],
                "home_club_code": g["home_club_code"], "away_club_code": g["away_club_code"]}
    pbp = conn.execute(
        """SELECT quarter, play_number, play_type, team_code, player_code,
                  minute, marker_time, points_a, points_b
           FROM pbp_events WHERE source=? AND season_code=? AND game_code=?""",
        (source, season_code, game_code),
    ).fetchall()
    tl = build_timeline([dict(r) for r in pbp], g["home_club_code"], g["away_club_code"])
    points = [
        {"t": e.abs_s, "quarter": e.quarter, "ot": e.ot,
         "home": e.home_after, "away": e.away_after,
         "play_type": e.play_type, "club_code": e.team_code,
         "player_code": e.player_code}
        for e in tl.events if e.delta_home or e.delta_away
    ]
    return {
        "game_code": game_code, "has_pbp": True,
        "home_club_code": tl.home_club, "away_club_code": tl.away_club,
        "home_final": tl.home_final, "away_final": tl.away_final,
        "duration": tl.duration, "n_ot": tl.n_ot, "points": points,
    }


def teams(conn, source: str, season_code: str, sort: str = "max_run",
          desc: bool = True) -> list[dict]:
    column = TEAM_SORTS[sort]
    order = "DESC" if desc else "ASC"
    rows = _rows(conn.execute(
        f"""SELECT t.*, s.club_name, t.games, t.possessions_avg,
                   t.fouls_drawn_per100, t.max_run, t.max_run_game,
                   t.max_blown_lead, t.max_blown_lead_game, t.clutch_pts_for,
                   t.clutch_pts_against, t.clutch_seconds,
                   s.wins, s.losses, s.point_diff, s.rank
            FROM team_season_metrics t
            LEFT JOIN standings s ON s.source=t.source AND s.season_code=t.season_code
                                 AND s.club_code=t.club_code
            WHERE t.source=? AND t.season_code=?
            ORDER BY t.{column} IS NULL, t.{column} {order}""",
        (source, season_code),
    ))
    for r in rows:
        r.update(_derived_team(r))
    return rows


def team(conn, source: str, season_code: str, club_code: str) -> dict | None:
    row = conn.execute(
        """SELECT t.*, s.club_name, s.wins, s.losses, s.point_diff, s.rank
           FROM team_season_metrics t
           LEFT JOIN standings s ON s.source=t.source AND s.season_code=t.season_code
                                AND s.club_code=t.club_code
           WHERE t.source=? AND t.season_code=? AND t.club_code=?""",
        (source, season_code, club_code),
    ).fetchone()
    if row is None:
        return None
    detail = dict(row)
    detail.update(_derived_team(detail))
    detail["radar"] = team_radar(conn, source, season_code, detail)
    detail["roster"] = _rows(conn.execute(
        """SELECT p.person_code AS player_code, p.name AS player_name, p.dorsal,
                  p.position_name, p.height, p.country_code, p.birth_date,
                  p.headshot_url,
                  m.games_played, m.seconds, m.points, m.pir_avg, m.pm_total
           FROM people p
           LEFT JOIN player_season_metrics m
                  ON m.source=p.source AND m.season_code=p.season_code
                 AND m.player_code=p.person_code
           WHERE p.source=? AND p.season_code=? AND p.club_code=? AND p.type_code='J'
           ORDER BY CASE WHEN p.dorsal GLOB '[0-9]*'
                         THEN CAST(p.dorsal AS INTEGER) ELSE 9999 END,
                    p.name""",
        (source, season_code, club_code),
    ))
    detail["games"] = _rows(conn.execute(
        """SELECT m.game_code, m.is_home, m.points, m.possessions, m.fouls_drawn,
                  m.max_run, m.max_lead, m.lost, m.clutch_pm,
                  g.utc_date, g.round,
                  CASE WHEN m.is_home THEN g.away_club_code ELSE g.home_club_code END
                    AS opponent_code,
                  CASE WHEN m.is_home THEN g.away_score ELSE g.home_score END
                    AS opponent_points
           FROM team_game_metrics m
           JOIN games g ON g.source=m.source AND g.season_code=m.season_code
                       AND g.game_code=m.game_code
           WHERE m.source=? AND m.season_code=? AND m.club_code=?
           ORDER BY m.game_code""",
        (source, season_code, club_code),
    ))
    return detail


def players(conn, source: str, season_code: str, *, sort: str = "pir_avg",
            desc: bool = True, club: str | None = None, min_games: int = 0,
            limit: int = 50, offset: int = 0) -> list[dict]:
    column = PLAYER_SORTS[sort]
    order = "DESC" if desc else "ASC"
    where = ["source=?", "season_code=?", "games_played >= ?"]
    params: list = [source, season_code, min_games]
    if club:
        where.append("clubs LIKE ?")
        params.append(f"%{club}%")
    params += [limit, offset]
    params = [source, season_code, *params]
    rows = _rows(conn.execute(
        f"""SELECT player_code, player_name, clubs, games_played, seconds, points,
                   reb_total, assists, steals, blocks_favour, turnovers, fouls_drawn,
                   pir_total, pir_avg, pir_per36, pm_total, pm_per36,
                   clutch_seconds, clutch_points, clutch_pm, fouls_drawn_per100,
                   reb_off, reb_def, fg2a, fg3m, fg3a, fta, poss_share,
                   opp_fgm, opp_fga, opp_points,
                   (SELECT p.headshot_url FROM people p
                     WHERE p.source=? AND p.season_code=?
                       AND p.person_code=player_season_metrics.player_code
                       AND p.headshot_url IS NOT NULL LIMIT 1) AS headshot_url
            FROM player_season_metrics WHERE {' AND '.join(where)}
            ORDER BY {column} IS NULL, {column} {order}, player_code
            LIMIT ? OFFSET ?""",
        params,
    ))
    for r in rows:
        r.update(_derived(r))
    return rows


def player(conn, source: str, season_code: str, player_code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM player_season_metrics WHERE source=? AND season_code=? AND player_code=?",
        (source, season_code, player_code),
    ).fetchone()
    if row is None:
        return None
    detail = dict(row)
    portrait = conn.execute(
        """SELECT headshot_url, action_url FROM people
           WHERE source=? AND season_code=? AND person_code=?
                 AND headshot_url IS NOT NULL LIMIT 1""",
        (source, season_code, player_code),
    ).fetchone()
    detail["headshot_url"] = portrait["headshot_url"] if portrait else None
    detail["action_url"] = portrait["action_url"] if portrait else None
    detail["radar"] = player_radar(conn, source, season_code, detail)
    detail["games"] = _rows(conn.execute(
        """SELECT m.game_code, m.club_code, m.is_home, m.pir, m.pm_computed,
                  m.seconds_computed, m.fouls_drawn, m.clutch_pm,
                  b.points, b.reb_total, b.assists, b.seconds_played,
                  g.utc_date, g.round,
                  CASE WHEN m.is_home THEN g.away_club_code ELSE g.home_club_code END
                    AS opponent_code
           FROM player_game_metrics m
           JOIN games g ON g.source=m.source AND g.season_code=m.season_code
                       AND g.game_code=m.game_code
           LEFT JOIN boxscore_lines b ON b.source=m.source AND b.season_code=m.season_code
                       AND b.game_code=m.game_code AND b.player_code=m.player_code
                       AND b.entry_type='player'
           WHERE m.source=? AND m.season_code=? AND m.player_code=?
           ORDER BY m.game_code""",
        (source, season_code, player_code),
    ))
    return detail


def index_runs(conn, source: str, season_code: str, limit: int = 25) -> list[dict]:
    return _rows(conn.execute(
        """SELECT m.game_code, m.club_code, m.max_run, m.max_run_detail, m.points,
                  g.utc_date, g.round,
                  CASE WHEN m.is_home THEN g.away_club_code ELSE g.home_club_code END
                    AS opponent_code
           FROM team_game_metrics m
           JOIN games g ON g.source=m.source AND g.season_code=m.season_code
                       AND g.game_code=m.game_code
           WHERE m.source=? AND m.season_code=? AND m.max_run IS NOT NULL
           ORDER BY m.max_run DESC, m.game_code LIMIT ?""",
        (source, season_code, limit),
    ))


def index_blown_leads(conn, source: str, season_code: str, limit: int = 25) -> list[dict]:
    """Biggest lead held by the club that ended up losing."""
    return _rows(conn.execute(
        """SELECT m.game_code, m.club_code, m.max_lead, m.points,
                  g.utc_date, g.round,
                  CASE WHEN m.is_home THEN g.away_club_code ELSE g.home_club_code END
                    AS opponent_code,
                  CASE WHEN m.is_home THEN g.away_score ELSE g.home_score END
                    AS opponent_points
           FROM team_game_metrics m
           JOIN games g ON g.source=m.source AND g.season_code=m.season_code
                       AND g.game_code=m.game_code
           WHERE m.source=? AND m.season_code=? AND m.lost=1 AND m.max_lead IS NOT NULL
           ORDER BY m.max_lead DESC, m.game_code LIMIT ?""",
        (source, season_code, limit),
    ))


def index_clutch(conn, source: str, season_code: str, limit: int = 25) -> dict:
    players_ = _rows(conn.execute(
        """SELECT player_code, player_name, clubs, clutch_seconds, clutch_points,
                  clutch_pm, games_played
           FROM player_season_metrics
           WHERE source=? AND season_code=? AND clutch_seconds > 0
           ORDER BY clutch_pm DESC, clutch_points DESC LIMIT ?""",
        (source, season_code, limit),
    ))
    teams_ = _rows(conn.execute(
        """SELECT t.club_code, s.club_name, t.clutch_pts_for, t.clutch_pts_against,
                  t.clutch_seconds,
                  t.clutch_pts_for - t.clutch_pts_against AS clutch_pm
           FROM team_season_metrics t
           LEFT JOIN standings s ON s.source=t.source AND s.season_code=t.season_code
                                AND s.club_code=t.club_code
           WHERE t.source=? AND t.season_code=?
           ORDER BY clutch_pm DESC""",
        (source, season_code),
    ))
    return {"players": players_, "teams": teams_}


def index_fouls_drawn(conn, source: str, season_code: str, limit: int = 25,
                      min_games: int = 5) -> dict:
    players_ = _rows(conn.execute(
        """SELECT player_code, player_name, clubs, games_played, fouls_drawn,
                  fouls_drawn_per100
           FROM player_season_metrics
           WHERE source=? AND season_code=? AND games_played >= ?
             AND fouls_drawn_per100 IS NOT NULL
           ORDER BY fouls_drawn_per100 DESC LIMIT ?""",
        (source, season_code, min_games, limit),
    ))
    teams_ = _rows(conn.execute(
        """SELECT t.club_code, s.club_name, t.games, t.fouls_drawn_per100,
                  t.possessions_avg
           FROM team_season_metrics t
           LEFT JOIN standings s ON s.source=t.source AND s.season_code=t.season_code
                                AND s.club_code=t.club_code
           WHERE t.source=? AND t.season_code=?
           ORDER BY t.fouls_drawn_per100 DESC""",
        (source, season_code),
    ))
    return {"players": players_, "teams": teams_}


def gauges(conn, source: str) -> dict[str, float]:
    """DB-backed numbers exported on /metrics."""
    out: dict[str, float] = {}
    row = conn.execute(
        """SELECT COUNT(*) games, SUM(pbp_status='missing') missing_pbp
           FROM games WHERE source=? AND is_final=1""",
        (source,),
    ).fetchone()
    out["games_ingested"] = float(row["games"] or 0)
    out["games_missing_pbp"] = float(row["missing_pbp"] or 0)
    run = conn.execute(
        """SELECT finished_at FROM ingest_runs WHERE ok=1 AND finished_at IS NOT NULL
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    out["last_successful_ingest_timestamp"] = _to_epoch(run["finished_at"]) if run else 0.0
    stamp = conn.execute(
        """SELECT value FROM metrics_meta WHERE key LIKE 'computed_at:%'
           ORDER BY value DESC LIMIT 1"""
    ).fetchone()
    out["metrics_computed_at_timestamp"] = _to_epoch(stamp["value"]) if stamp else 0.0
    return out


def _to_epoch(iso: str | None) -> float:
    from datetime import datetime
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return 0.0


def sqlite_backup(conn: sqlite3.Connection, dest: str) -> None:
    """VACUUM INTO — a consistent snapshot even while the writer is active."""
    conn.execute("VACUUM INTO ?", (dest,))
