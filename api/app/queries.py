"""Every SQL statement the API runs, one function per endpoint need.

Kept apart from the routers so the read model can be tested without HTTP and
so all column knowledge lives in one file. Functions return plain dicts/lists;
Pydantic models in app.models describe them to OpenAPI.

Reads only the tables `python -m metrics` fills (plus games/boxscore_lines
from ingest). The single exception is game_timeline(), which rebuilds the
score curve from pbp_events through metrics.timeline — see its docstring.
"""

from __future__ import annotations

import json
import sqlite3

from metrics.timeline import build_timeline

# --- sort whitelists ---------------------------------------------------------
# A column name cannot be a bound parameter, so anything that reaches ORDER BY
# must come from a fixed mapping — never from the request string itself.

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


# --- seasons -----------------------------------------------------------------

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


def list_seasons(conn, source: str) -> list[dict]:
    """Seasons with final games. `has_pbp` is false for the pre-2007 era,
    where the UI must label metrics as boxscore-only."""
    return _rows(conn.execute(
        """SELECT g.season_code, s.name AS season_name, s.year,
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


# --- standings ---------------------------------------------------------------

def clubs(conn, source: str, season_code: str) -> list[dict]:
    """Club registry for a season — the crest lookup the UI resolves by code,
    so no other endpoint has to carry an image URL on every row."""
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


# --- games -------------------------------------------------------------------

GAME_COLUMNS = """game_code, round, round_name, phase_type_code, utc_date, played,
                  home_club_code, home_club_name, home_score,
                  away_club_code, away_club_name, away_score,
                  winner_club_code, pbp_status"""


def games(conn, source: str, season_code: str, *, round_: int | None = None,
          club: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    where = ["source=?", "season_code=?", "is_final=1"]
    params: list = [source, season_code]
    if round_ is not None:
        where.append("round=?")
        params.append(round_)
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
    """Score worm — the one thing computed per request rather than stored.

    pbp_events keeps the raw feed: points_a/points_b are cumulative, NULL when
    unchanged, and nothing records whether "A" is the home side. build_timeline
    resolves all three (countdown clock → absolute seconds, carry-forward,
    majority-vote side inference) over ~550 rows, which is far cheaper than
    maintaining a redundant table. Only scoring events are returned — that is
    all a score curve needs.
    """
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


# --- teams -------------------------------------------------------------------

def teams(conn, source: str, season_code: str, sort: str = "max_run",
          desc: bool = True) -> list[dict]:
    column = TEAM_SORTS[sort]
    order = "DESC" if desc else "ASC"
    return _rows(conn.execute(
        f"""SELECT t.club_code, s.club_name, t.games, t.possessions_avg,
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


# --- players -----------------------------------------------------------------

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
    # The portrait comes from a correlated subquery rather than a JOIN: a player
    # has one `people` row per club/type, so joining would multiply the rows.
    # Its placeholders sit in the SELECT list, so they bind ahead of the rest.
    params = [source, season_code, *params]
    return _rows(conn.execute(
        f"""SELECT player_code, player_name, clubs, games_played, seconds, points,
                   reb_total, assists, steals, blocks_favour, turnovers, fouls_drawn,
                   pir_total, pir_avg, pir_per36, pm_total, pm_per36,
                   clutch_seconds, clutch_points, clutch_pm, fouls_drawn_per100,
                   (SELECT p.headshot_url FROM people p
                     WHERE p.source=? AND p.season_code=?
                       AND p.person_code=player_season_metrics.player_code
                       AND p.headshot_url IS NOT NULL LIMIT 1) AS headshot_url
            FROM player_season_metrics WHERE {' AND '.join(where)}
            ORDER BY {column} IS NULL, {column} {order}, player_code
            LIMIT ? OFFSET ?""",
        params,
    ))


def player(conn, source: str, season_code: str, player_code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM player_season_metrics WHERE source=? AND season_code=? AND player_code=?",
        (source, season_code, player_code),
    ).fetchone()
    if row is None:
        return None
    detail = dict(row)
    # Portrait, if the registry has one. A player can appear under several
    # club/type rows after a transfer; any row carries the same URLs.
    portrait = conn.execute(
        """SELECT headshot_url, action_url FROM people
           WHERE source=? AND season_code=? AND person_code=?
                 AND headshot_url IS NOT NULL LIMIT 1""",
        (source, season_code, player_code),
    ).fetchone()
    detail["headshot_url"] = portrait["headshot_url"] if portrait else None
    detail["action_url"] = portrait["action_url"] if portrait else None
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


# --- indexes (the signature metrics) ----------------------------------------

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


# --- operational gauges ------------------------------------------------------

def gauges(conn, source: str) -> dict[str, float]:
    """DB-backed numbers exported on /metrics.

    The CronJob pods are too short-lived for Prometheus to scrape, so the
    always-on API reports pipeline health by reading what the pipeline wrote.
    """
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
    """VACUUM INTO — a consistent snapshot even while the writer is active.

    Copying the file byte-for-byte could catch a torn WAL; this cannot.
    """
    conn.execute("VACUUM INTO ?", (dest,))
