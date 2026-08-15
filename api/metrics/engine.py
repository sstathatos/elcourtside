"""Orchestration: recompute all derived tables for a season from the Phase 1 tables."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from metrics import clutch as clutch_mod
from metrics import defense as defense_mod
from metrics import leads as leads_mod
from metrics import runs as runs_mod
from metrics.lineups import track_lineups
from metrics.pir import compute_pir
from metrics.plusminus import compute_plus_minus
from metrics.possessions import per_100, player_poss_share, team_possessions
from metrics.schema import ENGINE_VERSION, ensure_schema
from metrics.standings import compute_standings
from metrics.timeline import OT_LEN, REGULATION, build_timeline

log = logging.getLogger("metrics")

GAME_TABLES = ("player_game_metrics", "team_game_metrics")
SEASON_TABLES = ("player_season_metrics", "team_season_metrics", "standings")


@dataclass
class SeasonSummary:
    season_code: str
    games: int = 0
    pbp_games: int = 0
    lineup_anomalies: int = 0
    score_mismatches: int = 0


def compute_season(conn, source: str, season_code: str) -> SeasonSummary:
    ensure_schema(conn)
    summary = SeasonSummary(season_code=season_code)

    games = conn.execute(
        """SELECT game_code, phase_type_code, pbp_status,
                  home_club_code, home_club_name, home_score, home_partials,
                  away_club_code, away_club_name, away_score
           FROM games WHERE source=? AND season_code=? AND is_final=1
           ORDER BY game_code""",
        (source, season_code),
    ).fetchall()

    with conn:
        for table in GAME_TABLES + SEASON_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE source=? AND season_code=?",
                         (source, season_code))

        for g in games:
            _compute_game(conn, source, season_code, g, summary)
            summary.games += 1

        _rollup_players(conn, source, season_code)
        _rollup_teams(conn, source, season_code)
        _write_standings(conn, source, season_code)

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        for key, value in ((f"computed_at:{source}:{season_code}", now),
                           (f"engine_version:{source}:{season_code}", str(ENGINE_VERSION))):
            conn.execute("INSERT OR REPLACE INTO metrics_meta (key, value) VALUES (?, ?)",
                         (key, value))

    log.info("%s: %d games (%d with pbp), %d lineup anomalies, %d score mismatches",
             season_code, summary.games, summary.pbp_games,
             summary.lineup_anomalies, summary.score_mismatches)
    return summary


def _regulation_plus_partials(game) -> float:
    """Game duration for boxscore-only games, via extraPeriods in partials."""
    try:
        extra = json.loads(game["home_partials"] or "{}").get("extraPeriods") or {}
    except (ValueError, TypeError):
        extra = {}
    return REGULATION + OT_LEN * len(extra)


def _compute_game(conn, source, season_code, game, summary: SeasonSummary) -> None:
    game_code = game["game_code"]
    home, away = game["home_club_code"], game["away_club_code"]

    lines = conn.execute(
        """SELECT * FROM boxscore_lines
           WHERE source=? AND season_code=? AND game_code=?""",
        (source, season_code, game_code),
    ).fetchall()
    players = [r for r in lines if r["entry_type"] == "player"]
    totals = {r["is_home"]: r for r in lines if r["entry_type"] == "total"}

    timeline = lineups = pm = clutch_stats = run_best = lead_stats = None
    defense = None
    if game["pbp_status"] == "ok":
        pbp = conn.execute(
            """SELECT quarter, play_number, play_type, team_code, player_code,
                      minute, marker_time, points_a, points_b
               FROM pbp_events WHERE source=? AND season_code=? AND game_code=?""",
            (source, season_code, game_code),
        ).fetchall()
        if pbp:
            timeline = build_timeline([dict(r) for r in pbp], home, away)
            starters_home = {r["player_code"] for r in players if r["is_home"] and r["start_five"]}
            starters_away = {r["player_code"] for r in players if not r["is_home"] and r["start_five"]}
            lineups = track_lineups(timeline, starters_home, starters_away)
            pm = compute_plus_minus(timeline, lineups)
            defense = defense_mod.compute_on_court_defense(timeline, lineups)
            clutch_stats = clutch_mod.compute_clutch(timeline, lineups)
            run_best = runs_mod.max_runs(timeline)
            lead_stats = leads_mod.compute_leads(timeline)
            summary.pbp_games += 1
            summary.lineup_anomalies += len(lineups.anomalies)
            if (timeline.home_final, timeline.away_final) != (game["home_score"], game["away_score"]):
                summary.score_mismatches += 1
                log.warning("%s g%s: pbp score %d-%d != boxscore %s-%s",
                            season_code, game_code, timeline.home_final,
                            timeline.away_final, game["home_score"], game["away_score"])

    duration = timeline.duration if timeline else _regulation_plus_partials(game)
    poss = {side: team_possessions(t) for side, t in totals.items()}

    player_rows = []
    for line in players:
        side = line["is_home"]
        has_pbp = timeline is not None
        p = line["player_code"]
        player_rows.append({
            "player_code": p,
            "club_code": home if side else away,
            "is_home": side,
            "pir": compute_pir(line),
            "pm_computed": pm.get(p, 0) if has_pbp else None,
            "seconds_computed": lineups.seconds.get(p, 0.0) if has_pbp else None,
            "poss_share": player_poss_share(poss.get(side, 0.0), line["seconds_played"], duration),
            "fouls_drawn": line["fouls_received"] or 0,
            "clutch_seconds": clutch_stats.player_seconds.get(p, 0.0) if has_pbp else None,
            "clutch_points": clutch_stats.player_points.get(p, 0) if has_pbp else None,
            "clutch_pm": clutch_stats.player_pm.get(p, 0) if has_pbp else None,
            "opp_fgm": defense.opp_fgm.get(p, 0) if defense else None,
            "opp_fga": defense.opp_fga.get(p, 0) if defense else None,
            "opp_points": defense.opp_points.get(p, 0) if defense else None,
        })
    conn.executemany(
        """INSERT INTO player_game_metrics
           (source, season_code, game_code, player_code, club_code, is_home, pir,
            pm_computed, seconds_computed, poss_share, fouls_drawn,
            clutch_seconds, clutch_points, clutch_pm, opp_fgm, opp_fga, opp_points)
           VALUES (:source, :season_code, :game_code, :player_code, :club_code,
                   :is_home, :pir, :pm_computed, :seconds_computed, :poss_share,
                   :fouls_drawn, :clutch_seconds, :clutch_points, :clutch_pm,
                   :opp_fgm, :opp_fga, :opp_points)""",
        [{**r, "source": source, "season_code": season_code, "game_code": game_code}
         for r in player_rows],
    )

    team_rows = []
    for side, club in ((1, home), (0, away)):
        total = totals.get(side)
        score = game["home_score"] if side else game["away_score"]
        opp_score = game["away_score"] if side else game["home_score"]
        run = run_best[club] if run_best else None
        team_rows.append({
            "club_code": club,
            "is_home": side,
            "points": score,
            "possessions": poss.get(side),
            "fouls_drawn": total["fouls_received"] if total else None,
            "max_run": run.points if run else None,
            "max_run_detail": json.dumps(
                {"points": run.points, "start_s": run.start_s, "end_s": run.end_s}
            ) if run else None,
            "max_lead": lead_stats.max_lead[club] if lead_stats else None,
            "lost": 1 if (score or 0) < (opp_score or 0) else 0,
            "clutch_pts_for": (clutch_stats.home_pts_for if side else clutch_stats.away_pts_for)
                              if clutch_stats else None,
            "clutch_pts_against": (clutch_stats.away_pts_for if side else clutch_stats.home_pts_for)
                                  if clutch_stats else None,
            "clutch_pm": ((clutch_stats.home_pts_for - clutch_stats.away_pts_for) * (1 if side else -1))
                         if clutch_stats else None,
            "clutch_seconds": clutch_stats.game_seconds if clutch_stats else None,
            "lineup_anomalies": len(lineups.anomalies) if lineups else None,
        })
    conn.executemany(
        """INSERT INTO team_game_metrics
           (source, season_code, game_code, club_code, is_home, points, possessions,
            fouls_drawn, max_run, max_run_detail, max_lead, lost, clutch_pts_for,
            clutch_pts_against, clutch_pm, clutch_seconds, lineup_anomalies)
           VALUES (:source, :season_code, :game_code, :club_code, :is_home, :points,
                   :possessions, :fouls_drawn, :max_run, :max_run_detail, :max_lead,
                   :lost, :clutch_pts_for, :clutch_pts_against, :clutch_pm,
                   :clutch_seconds, :lineup_anomalies)""",
        [{**r, "source": source, "season_code": season_code, "game_code": game_code}
         for r in team_rows],
    )


def _rollup_players(conn, source: str, season_code: str) -> None:
    conn.execute(
        """INSERT INTO player_season_metrics
           (source, season_code, player_code, player_name, clubs, games_played,
            seconds, points, reb_total, assists, steals, blocks_favour,
            turnovers, fouls_drawn, pir_total, pir_avg, pir_per36, pm_total,
            pm_per36, clutch_seconds, clutch_points, clutch_pm,
            fouls_drawn_per100, reb_off, reb_def, fg2m, fg2a, fg3m, fg3a,
            ftm, fta, opp_fgm, opp_fga, opp_points, poss_share)
           SELECT b.source, b.season_code, b.player_code,
                  MAX(b.player_name),
                  GROUP_CONCAT(DISTINCT b.club_code),
                  SUM(b.seconds_played > 0),
                  SUM(b.seconds_played),
                  SUM(b.points), SUM(b.reb_total), SUM(b.assists), SUM(b.steals),
                  SUM(b.blocks_favour), SUM(b.turnovers), SUM(b.fouls_received),
                  SUM(m.pir),
                  CAST(SUM(m.pir) AS REAL) / NULLIF(SUM(b.seconds_played > 0), 0),
                  36.0 * 60 * SUM(m.pir) / NULLIF(SUM(b.seconds_played), 0),
                  SUM(m.pm_computed),
                  36.0 * 60 * SUM(m.pm_computed) / NULLIF(SUM(b.seconds_played), 0),
                  SUM(m.clutch_seconds), SUM(m.clutch_points), SUM(m.clutch_pm),
                  100.0 * SUM(b.fouls_received) / NULLIF(SUM(m.poss_share), 0),
                  SUM(b.reb_off), SUM(b.reb_def),
                  SUM(b.fg2m), SUM(b.fg2a), SUM(b.fg3m), SUM(b.fg3a),
                  SUM(b.ftm), SUM(b.fta),
                  SUM(m.opp_fgm), SUM(m.opp_fga), SUM(m.opp_points),
                  SUM(m.poss_share)
           FROM boxscore_lines b
           JOIN player_game_metrics m
             ON m.source = b.source AND m.season_code = b.season_code
            AND m.game_code = b.game_code AND m.player_code = b.player_code
           WHERE b.source = ? AND b.season_code = ?
             AND b.entry_type = 'player' AND b.player_code != ''
           GROUP BY b.player_code""",
        (source, season_code),
    )


def _rollup_teams(conn, source: str, season_code: str) -> None:
    conn.execute(
        """INSERT INTO team_season_metrics
           (source, season_code, club_code, games, possessions_avg,
            fouls_drawn_per100, max_run, max_run_game, max_blown_lead,
            max_blown_lead_game, clutch_pts_for, clutch_pts_against,
            clutch_seconds, points, fg2m, fg2a, fg3m, fg3a, ftm, fta,
            reb_off, reb_def, assists, steals, blocks_favour, turnovers,
            possessions, opp_points, opp_fg2m, opp_fg2a, opp_fg3m, opp_fg3a,
            opp_ftm, opp_fta, opp_reb_off, opp_reb_def, opp_turnovers,
            opp_possessions)
           SELECT t.source, t.season_code, t.club_code,
                  COUNT(*),
                  AVG(t.possessions),
                  100.0 * SUM(t.fouls_drawn) / NULLIF(SUM(t.possessions), 0),
                  MAX(t.max_run),
                  (SELECT x.game_code FROM team_game_metrics x
                    WHERE x.source = t.source AND x.season_code = t.season_code
                      AND x.club_code = t.club_code AND x.max_run IS NOT NULL
                    ORDER BY x.max_run DESC LIMIT 1),
                  MAX(CASE WHEN t.lost = 1 THEN t.max_lead END),
                  (SELECT x.game_code FROM team_game_metrics x
                    WHERE x.source = t.source AND x.season_code = t.season_code
                      AND x.club_code = t.club_code AND x.lost = 1
                      AND x.max_lead IS NOT NULL
                    ORDER BY x.max_lead DESC LIMIT 1),
                  SUM(t.clutch_pts_for), SUM(t.clutch_pts_against), SUM(t.clutch_seconds),
                  SUM(own.points), SUM(own.fg2m), SUM(own.fg2a),
                  SUM(own.fg3m), SUM(own.fg3a), SUM(own.ftm), SUM(own.fta),
                  SUM(own.reb_off), SUM(own.reb_def), SUM(own.assists),
                  SUM(own.steals), SUM(own.blocks_favour), SUM(own.turnovers),
                  SUM(t.possessions),
                  SUM(opp.points), SUM(opp.fg2m), SUM(opp.fg2a),
                  SUM(opp.fg3m), SUM(opp.fg3a), SUM(opp.ftm), SUM(opp.fta),
                  SUM(opp.reb_off), SUM(opp.reb_def), SUM(opp.turnovers),
                  SUM(o.possessions)
           FROM team_game_metrics t
           JOIN boxscore_lines own
             ON own.source = t.source AND own.season_code = t.season_code
            AND own.game_code = t.game_code AND own.is_home = t.is_home
            AND own.entry_type = 'total'
           JOIN boxscore_lines opp
             ON opp.source = t.source AND opp.season_code = t.season_code
            AND opp.game_code = t.game_code AND opp.is_home <> t.is_home
            AND opp.entry_type = 'total'
           JOIN team_game_metrics o
             ON o.source = t.source AND o.season_code = t.season_code
            AND o.game_code = t.game_code AND o.is_home <> t.is_home
           WHERE t.source = ? AND t.season_code = ?
           GROUP BY t.club_code""",
        (source, season_code),
    )


def _write_standings(conn, source: str, season_code: str) -> None:
    games = [dict(r) for r in conn.execute(
        """SELECT home_club_code, home_club_name, home_score,
                  away_club_code, away_club_name, away_score
           FROM games WHERE source=? AND season_code=? AND played=1
             AND phase_type_code='RS'""",
        (source, season_code),
    )]
    if not games:
        return
    table = compute_standings(games)
    conn.executemany(
        """INSERT INTO standings
           (source, season_code, club_code, club_name, games, wins, losses,
            points_for, points_against, point_diff, rank)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(source, season_code, r.club_code, r.club_name, r.games, r.wins,
          r.losses, r.points_for, r.points_against, r.point_diff, r.rank)
         for r in table],
    )
