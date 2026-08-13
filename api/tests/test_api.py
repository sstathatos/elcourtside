"""API tests — the real game-1 fixtures ingested, computed, then served.

Same DB recipe as test_engine.py, so what the endpoints return is the actual
output of the metrics engine rather than hand-written rows.
"""

import sqlite3

import pytest
from conftest import load_fixture
from fastapi.testclient import TestClient

from app import cache
from app.db import get_conn
from app.main import app
from ingest import db
from ingest.sources.euroleague import parse_boxscore, parse_pbp
from metrics import engine
from metrics.schema import ensure_schema

SRC = "euroleague"
SEASON = "E2025"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_conn():
    # shared with the TestClient's server thread, hence check_same_thread=False
    conn = db.connect(":memory:", check_same_thread=False)
    ensure_schema(conn)
    db.upsert_seasons(conn, SRC, [{
        "code": SEASON, "name": "2025-26", "alias": "E2025", "year": 2025,
        "start_date": None, "end_date": None, "winner_club_code": None,
    }])
    db.upsert_games(conn, SRC, [{
        "season_code": SEASON, "game_code": 1, "identifier": "E2025_1",
        "utc_date": "2025-09-30T18:00:00Z", "local_date": None, "round": 1,
        "round_name": "Round 1", "phase_type_code": "RS", "phase_type_name": "RS",
        "group_name": "", "played": 1, "game_status": "Confirmed",
        "home_club_code": "IST", "home_club_name": "Anadolu Efes Istanbul",
        "home_score": 85, "away_club_code": "TEL", "away_club_name": "Maccabi Tel Aviv",
        "away_score": 78, "home_partials": None, "away_partials": None,
        "winner_club_code": "IST", "audience": 0,
    }], "t0")
    db.set_game_ingest_state(conn, SRC, SEASON, 1, "ok", "ok", 1, "t0")
    db.replace_boxscore_lines(conn, SRC, SEASON, 1,
                              parse_boxscore(load_fixture("game1_stats.json"), "IST", "TEL"))
    pbp_rows, _live = parse_pbp(load_fixture("game1_pbp.json"))
    db.replace_pbp_events(conn, SRC, SEASON, 1, pbp_rows)
    # TEL deliberately has no crest: the null path has to survive the API.
    db.upsert_clubs(conn, SRC, SEASON, [
        {"club_code": "IST", "club_name": "Anadolu Efes Istanbul",
         "crest_url": "https://cdn.example/ist.png"},
        {"club_code": "TEL", "club_name": "Maccabi Tel Aviv", "crest_url": None},
    ])
    conn.commit()
    engine.compute_season(conn, SRC, SEASON)
    return conn


def _person(code: str, club: str, headshot: str | None) -> dict:
    return {
        "person_code": code, "club_code": club, "type_code": "J", "name": "X",
        "type_name": "Player", "active": 1, "dorsal": "0", "position": 1,
        "position_name": "G", "height": 200, "birth_date": None,
        "country_code": "GRE", "start_date": None, "end_date": None,
        "headshot_url": headshot, "action_url": headshot,
    }


@pytest.fixture
def client(api_conn):
    app.dependency_overrides[get_conn] = lambda: api_conn
    with TestClient(app, client=("127.0.0.1", 5000)) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def player_code(api_conn):
    return api_conn.execute(
        "SELECT player_code FROM player_season_metrics ORDER BY pir_total DESC LIMIT 1"
    ).fetchone()["player_code"]


ROUTES = [
    "/api/seasons",
    "/api/standings",
    "/api/games",
    "/api/games/1",
    "/api/games/1/timeline",
    "/api/teams",
    "/api/teams/IST",
    "/api/players",
    "/api/players?sort=pm_per36&desc=false&limit=5",
    "/api/indexes/runs",
    "/api/indexes/blown-leads",
    "/api/indexes/clutch",
    "/api/indexes/fouls-drawn?min_games=0",
]


@pytest.mark.parametrize("route", ROUTES)
def test_route_serves_data(client, route):
    r = client.get(route)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body, f"{route} returned an empty body"
    assert r.headers["etag"] and "max-age" in r.headers["cache-control"]


def test_standings_matches_the_engine(client):
    rows = client.get("/api/standings").json()
    assert [(r["club_code"], r["wins"], r["losses"]) for r in rows] == [
        ("IST", 1, 0), ("TEL", 0, 1)]


def test_game_detail_and_timeline(client):
    game = client.get("/api/games/1").json()
    assert game["home_score"] == 85 and game["away_score"] == 78
    assert len(game["team_metrics"]) == 2 and game["boxscore"]

    tl = client.get("/api/games/1/timeline").json()
    assert tl["has_pbp"] is True
    assert (tl["home_final"], tl["away_final"]) == (85, 78)
    # a score curve is monotonic in both series and ends at the final score
    assert tl["points"][-1]["home"] == 85 and tl["points"][-1]["away"] == 78
    assert all(b["home"] >= a["home"] and b["away"] >= a["away"]
               for a, b in zip(tl["points"], tl["points"][1:]))


def test_player_detail(client, player_code):
    r = client.get(f"/api/players/{player_code}")
    assert r.status_code == 200
    body = r.json()
    assert body["player_code"] == player_code
    assert len(body["games"]) == 1


def test_unknown_things_are_404(client, player_code):
    assert client.get("/api/games/9999").status_code == 404
    assert client.get("/api/players/NOPE").status_code == 404
    assert client.get("/api/teams/NOPE").status_code == 404
    assert client.get("/api/standings?season=E1999").status_code == 404
    assert "not found" in client.get("/api/games/9999").json()["detail"]


def test_sort_whitelist_rejects_injection(client):
    r = client.get("/api/players?sort=pir_avg;DROP TABLE games")
    assert r.status_code == 422
    assert client.get("/api/players?limit=100000").status_code == 422
    # the table is obviously still there
    assert client.get("/api/games").status_code == 200


def test_cache_serves_repeat_requests_without_requerying(client):
    client.get("/api/standings")
    misses = cache.stats()["misses"]
    body = client.get("/api/standings").json()
    assert cache.stats()["misses"] == misses, "second request rebuilt the response"
    assert cache.stats()["hits"] > 0 and body


def test_recompute_busts_the_cache(client, api_conn):
    first = client.get("/api/standings")
    api_conn.execute("UPDATE standings SET wins = 99 WHERE club_code='IST'")
    api_conn.commit()
    assert client.get("/api/standings").json()[0]["wins"] == 1, "stale entry expected"

    cache._stamps.clear()          # skip the 5 s stamp memo
    engine.compute_season(api_conn, SRC, SEASON)   # new computed_at
    second = client.get("/api/standings")
    assert second.headers["etag"] != first.headers["etag"]


def test_etag_returns_304(client):
    first = client.get("/api/standings")
    again = client.get("/api/standings", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert not again.content


def test_health_and_metrics(client):
    health = client.get("/health").json()
    assert health["status"] in {"ok", "degraded"}
    body = client.get("/metrics").text
    assert "http_requests_total" in body or "http_request_duration" in body


def test_backup_streams_a_valid_database(client, tmp_path):
    r = client.get("/internal/backup.sqlite")
    assert r.status_code == 200
    path = tmp_path / "backup.sqlite"
    path.write_bytes(r.content)
    copy = sqlite3.connect(path)
    tables = {row[0] for row in copy.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"games", "pbp_events", "player_game_metrics"} <= tables
    assert copy.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    copy.close()


def test_backup_refuses_external_callers(api_conn):
    app.dependency_overrides[get_conn] = lambda: api_conn
    # a genuinely public address — Python counts the TEST-NET ranges as private
    with TestClient(app, client=("8.8.8.8", 5000)) as external:
        assert external.get("/internal/backup.sqlite").status_code == 403
    app.dependency_overrides.clear()


# --- crests and portraits ----------------------------------------------------

def test_clubs_endpoint_carries_crests_and_tolerates_missing_ones(client):
    rows = {c["club_code"]: c for c in client.get("/api/clubs").json()}
    assert rows["IST"]["crest_url"] == "https://cdn.example/ist.png"
    assert rows["IST"]["club_name"] == "Anadolu Efes Istanbul"
    # a club the registry has no crest for still appears, just without an image
    assert rows["TEL"]["crest_url"] is None


def test_player_detail_exposes_headshot_and_action(client, api_conn, player_code):
    db.upsert_people(api_conn, SRC, SEASON,
                     [_person(player_code, "IST", "https://cdn.example/p.png")])
    api_conn.commit()
    cache.clear()
    body = client.get(f"/api/players/{player_code}").json()
    assert body["headshot_url"] == "https://cdn.example/p.png"
    assert body["action_url"] == "https://cdn.example/p.png"


def test_player_without_a_registry_photo_reports_null(client, player_code):
    body = client.get(f"/api/players/{player_code}").json()
    assert body["headshot_url"] is None
    assert body["action_url"] is None


def test_players_list_carries_headshots_without_duplicating_rows(
        client, api_conn, player_code):
    # a transferred player has one `people` row per club — the list must still
    # return exactly one row for them (the reason the query uses a subquery
    # rather than a JOIN)
    db.upsert_people(api_conn, SRC, SEASON, [
        _person(player_code, "IST", "https://cdn.example/p.png"),
        _person(player_code, "TEL", "https://cdn.example/p.png"),
    ])
    api_conn.commit()
    cache.clear()
    rows = client.get("/api/players?limit=500").json()
    assert [r["player_code"] for r in rows].count(player_code) == 1
    hit = next(r for r in rows if r["player_code"] == player_code)
    assert hit["headshot_url"] == "https://cdn.example/p.png"


def test_team_roster_lists_the_registered_squad(client, api_conn):
    # 7 has no metrics row: a signing who has not played yet must still appear
    db.upsert_people(api_conn, SRC, SEASON, [
        {**_person("111111", "IST", None), "name": "SUB, TEN", "dorsal": "10"},
        {**_person("222222", "IST", None), "name": "SUB, TWO", "dorsal": "2"},
        {**_person("333333", "TEL", None), "name": "OTHER, CLUB", "dorsal": "5"},
    ])
    api_conn.commit()
    cache.clear()
    roster = client.get("/api/teams/IST").json()["roster"]
    names = [r["player_name"] for r in roster]
    # only this club's players, shirt numbers ordered numerically not as text
    assert "OTHER, CLUB" not in names
    assert [r["dorsal"] for r in roster if r["dorsal"] in {"2", "10"}] == ["2", "10"]
    unplayed = next(r for r in roster if r["player_name"] == "SUB, TEN")
    assert unplayed["games_played"] is None


def test_response_shape_version_changes_the_etag(client, monkeypatch):
    before = client.get("/api/teams/IST").headers["etag"]
    # a shape change with no recompute must still retire cached copies,
    # otherwise browsers revalidate into a 304 and keep the old body forever
    monkeypatch.setattr(cache, "SCHEMA_VERSION", "test-next")
    cache.clear()
    after = client.get("/api/teams/IST").headers["etag"]
    assert before != after


# --- radar -------------------------------------------------------------------

def test_percentile_uses_the_midpoint_rule_for_ties():
    from app.queries import _percentile
    assert _percentile([1, 2, 3, 4], 5) == 100.0
    assert _percentile([1, 2, 3, 4], 0) == 0.0
    # an all-level field lands mid-scale, not at an extreme
    assert _percentile([7, 7, 7], 7) == 50.0
    assert _percentile([], 3) == 0.0


def test_team_radar_ranks_against_the_league(client):
    won = client.get("/api/teams/IST").json()["radar"]
    lost = client.get("/api/teams/TEL").json()["radar"]
    assert [a["key"] for a in won]
    assert all(0 <= a["percentile"] <= 100 for a in won)
    # a club is ranked inside its own league, so the leader of a two-club field
    # sits at 75 (midpoint rule), not 100 — what matters is the ordering
    ist = next(a for a in won if a["key"] == "point_diff")
    tel = next(a for a in lost if a["key"] == "point_diff")
    assert ist["percentile"] > tel["percentile"]
    assert ist["value"] > 0 > tel["value"]


def test_player_radar_needs_a_real_sample(client, player_code):
    # the fixture has a single game, well under the games threshold, so a
    # per-36 rate would be noise and the radar is withheld rather than invented
    assert client.get(f"/api/players/{player_code}").json()["radar"] == []


# --- 12-axis skill radar -----------------------------------------------------

def test_radar_flips_percentiles_where_lower_is_better():
    from app.queries import _radar
    axes = [("tov", "Ball Security", "tov100", True),
            ("pts", "PTS", "pts36", False)]
    field = [{"tov100": 1.0, "pts36": 10.0},
             {"tov100": 2.0, "pts36": 20.0},
             {"tov100": 3.0, "pts36": 30.0}]
    # fewest turnovers in the field must rank top, most must rank bottom
    best = {a["key"]: a for a in _radar(field, field[0], axes)}
    worst = {a["key"]: a for a in _radar(field, field[2], axes)}
    assert best["tov"]["percentile"] > worst["tov"]["percentile"]
    assert best["tov"]["lower_is_better"] is True
    # a normal axis is untouched: most points ranks top
    assert best["pts"]["percentile"] < worst["pts"]["percentile"]
    assert worst["pts"]["lower_is_better"] is False


def test_derived_shooting_metrics():
    from app.queries import _derived
    # 10 pts on 4 FGA (2 of them threes) and 2 FTA:
    #   TS% = 100 * 10 / (2 * (4 + 0.44*2)) = 1000 / 9.76 = 102.46
    row = {"points": 10, "seconds": 2160.0, "poss_share": 50.0,
           "fg2a": 2, "fg3m": 1, "fg3a": 2, "fta": 2, "turnovers": 5}
    d = _derived(row)
    assert round(d["ts_pct"], 2) == 102.46
    assert d["pts36"] == 10.0                       # exactly 36 minutes played
    assert d["tov100"] == 10.0                      # 5 per 50 possessions
    # 2 three-point attempts is far below the threshold, so no percentage
    assert d["fg3_pct"] is None


def test_derived_guards_thin_samples_and_missing_defence():
    from app.queries import _derived, MIN_FG3A
    row = {"points": 100, "seconds": 2160.0, "poss_share": 0,
           "fg3m": 10, "fg3a": MIN_FG3A, "opp_fga": 3, "opp_fgm": 2}
    d = _derived(row)
    assert d["fg3_pct"] == 50.0          # exactly at the threshold, so counted
    assert d["opp_fg_pct"] is None       # 3 opponent attempts is noise
    assert d["tov100"] is None           # no possessions, no rate
    assert d["drtg"] is None


def test_player_radar_has_twelve_axes_with_real_data(client, api_conn, player_code):
    # the fixture is one game, below the games threshold — so relax it
    import app.queries as q
    original = q.RADAR_MIN_GAMES
    q.RADAR_MIN_GAMES = 1
    try:
        cache.clear()
        radar = client.get(f"/api/players/{player_code}").json()["radar"]
    finally:
        q.RADAR_MIN_GAMES = original
    keys = [a["key"] for a in radar]
    # every axis present is one we declared, and the inverted ones are flagged
    assert set(keys) <= {k for k, _, _, _ in q.PLAYER_RADAR}
    assert all(0 <= a["percentile"] <= 100 for a in radar)
    inverted = {a["key"] for a in radar if a.get("lower_is_better")}
    assert inverted <= {"ball_security", "opp_fg_pct", "drtg"}


def test_player_page_survives_a_database_without_radar_columns(client, api_conn, player_code):
    """A deploy ships the image before the metrics job adds new columns, so the
    API must serve an older database — losing the chart, not the page."""
    api_conn.executescript(
        "ALTER TABLE player_season_metrics DROP COLUMN reb_off;"
        "ALTER TABLE team_season_metrics ADD COLUMN _unused INTEGER;"
    )
    api_conn.commit()
    cache.clear()
    r = client.get(f"/api/players/{player_code}")
    assert r.status_code == 200, r.text
    assert r.json()["radar"] == []
