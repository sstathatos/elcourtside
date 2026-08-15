"""Integration: full real game (E2025 game 1, IST 85-78 TEL) through the whole engine, validated against the official boxscore ground truth."""

import pytest

from conftest import load_fixture

from ingest import db
from ingest.sources.euroleague import parse_boxscore, parse_pbp
from metrics import engine
from metrics.schema import ensure_schema

SRC = "euroleague"
SEASON = "E2025"


def game_row(code=1, phase="RS", **over):
    row = {
        "season_code": SEASON, "game_code": code, "identifier": f"{SEASON}_{code}",
        "utc_date": "2025-09-30T18:00:00Z", "local_date": None, "round": 1,
        "round_name": "Round 1", "phase_type_code": phase, "phase_type_name": phase,
        "group_name": "", "played": 1, "game_status": "Confirmed",
        "home_club_code": "IST", "home_club_name": "Anadolu Efes Istanbul",
        "home_score": 85, "away_club_code": "TEL", "away_club_name": "Maccabi Tel Aviv",
        "away_score": 78, "home_partials": None, "away_partials": None,
        "winner_club_code": "IST", "audience": 0,
    }
    row.update(over)
    return row


@pytest.fixture
def game_conn(conn):
    ensure_schema(conn)
    db.upsert_games(conn, SRC, [game_row()], "t0")
    db.set_game_ingest_state(conn, SRC, SEASON, 1, "ok", "ok", 1, "t0")
    box = parse_boxscore(load_fixture("game1_stats.json"), "IST", "TEL")
    db.replace_boxscore_lines(conn, SRC, SEASON, 1, box)
    pbp_rows, live = parse_pbp(load_fixture("game1_pbp.json"))
    assert pbp_rows and not live
    db.replace_pbp_events(conn, SRC, SEASON, 1, pbp_rows)
    conn.commit()
    return conn


def test_engine_full_real_game(game_conn):
    summary = engine.compute_season(game_conn, SRC, SEASON)
    assert summary.games == 1 and summary.pbp_games == 1
    assert summary.score_mismatches == 0

    bad = game_conn.execute(
        """SELECT b.player_name, m.pir, b.valuation FROM player_game_metrics m
           JOIN boxscore_lines b ON b.source=m.source AND b.season_code=m.season_code
             AND b.game_code=m.game_code AND b.player_code=m.player_code
             AND b.entry_type='player'
           WHERE m.pir != b.valuation""").fetchall()
    assert bad == [], [dict(r) for r in bad]

    pm = game_conn.execute(
        """SELECT b.player_name, m.pm_computed, b.plus_minus FROM player_game_metrics m
           JOIN boxscore_lines b ON b.source=m.source AND b.season_code=m.season_code
             AND b.game_code=m.game_code AND b.player_code=m.player_code
             AND b.entry_type='player'""").fetchall()
    mismatches = [dict(r) for r in pm if r["pm_computed"] != r["plus_minus"]]
    assert mismatches == []

    secs = game_conn.execute(
        """SELECT b.player_name, m.seconds_computed, b.seconds_played
           FROM player_game_metrics m
           JOIN boxscore_lines b ON b.source=m.source AND b.season_code=m.season_code
             AND b.game_code=m.game_code AND b.player_code=m.player_code
             AND b.entry_type='player'""").fetchall()
    off = [dict(r) for r in secs
           if abs((r["seconds_computed"] or 0) - (r["seconds_played"] or 0)) > 60]
    assert off == []

    team = {r["club_code"]: dict(r) for r in game_conn.execute(
        "SELECT * FROM team_game_metrics")}
    assert team["IST"]["points"] == 85 and team["TEL"]["points"] == 78
    assert team["TEL"]["lost"] == 1 and team["IST"]["lost"] == 0
    assert team["IST"]["max_run"] >= 4 and team["IST"]["max_lead"] >= 7
    assert team["IST"]["possessions"] == pytest.approx(team["TEL"]["possessions"], rel=0.15)

    st = game_conn.execute("SELECT * FROM standings ORDER BY rank").fetchall()
    assert [ (r["club_code"], r["wins"], r["losses"]) for r in st ] == [("IST", 1, 0), ("TEL", 0, 1)]


def test_engine_idempotent(game_conn):
    engine.compute_season(game_conn, SRC, SEASON)
    counts1 = {t: game_conn.execute(f"SELECT count(*) c FROM {t}").fetchone()["c"]
               for t in ("player_game_metrics", "team_game_metrics",
                         "player_season_metrics", "team_season_metrics", "standings")}
    engine.compute_season(game_conn, SRC, SEASON)
    counts2 = {t: game_conn.execute(f"SELECT count(*) c FROM {t}").fetchone()["c"]
               for t in counts1}
    assert counts1 == counts2
    assert counts1["player_game_metrics"] > 0


def test_engine_boxscore_only_game(game_conn):
    game_conn.execute("UPDATE games SET pbp_status='missing'")
    game_conn.execute("DELETE FROM pbp_events")
    game_conn.commit()
    summary = engine.compute_season(game_conn, SRC, SEASON)
    assert summary.games == 1 and summary.pbp_games == 0
    row = game_conn.execute(
        "SELECT pir, pm_computed, poss_share FROM player_game_metrics LIMIT 1").fetchone()
    assert row["pir"] is not None
    assert row["pm_computed"] is None
    ps = game_conn.execute(
        "SELECT pm_total, pir_total FROM player_season_metrics LIMIT 1").fetchone()
    assert ps["pm_total"] is None and ps["pir_total"] is not None
