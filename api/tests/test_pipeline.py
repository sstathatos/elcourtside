"""Pipeline tests with a fake in-memory source: verifies season selection, final-game bookkeeping (never re-fetch), live handling, and missing PBP."""

from ingest import db, pipeline
from ingest.sources.base import FetchedGameDetail, FetchedList, Source


def season_row(code, year):
    return {"code": code, "name": code, "alias": code, "year": year,
            "start_date": None, "end_date": None, "winner_club_code": None}


def game_row(season, code, played=1):
    return {"season_code": season, "game_code": code, "identifier": f"{season}_{code}",
            "utc_date": "2025-10-01T18:00:00Z", "local_date": None, "round": 1,
            "round_name": "Round 1", "phase_type_code": "RS", "phase_type_name": "RS",
            "group_name": "", "played": played, "game_status": "Confirmed",
            "home_club_code": "AAA", "home_club_name": "A", "home_score": 80 if played else None,
            "away_club_code": "BBB", "away_club_name": "B", "away_score": 70 if played else None,
            "home_partials": None, "away_partials": None,
            "winner_club_code": "AAA" if played else None, "audience": 0}


def pbp_row(n):
    return {"quarter": 1, "play_number": n, "play_type": "BP", "team_code": "",
            "player_code": "", "player_name": None, "dorsal": None, "minute": 1,
            "marker_time": "", "points_a": None, "points_b": None,
            "play_info": "Begin Period", "comment": ""}


def box_row(code):
    return {"is_home": 1, "entry_type": "player", "player_code": code,
            "club_code": "AAA", "player_name": "X", "dorsal": "1", "start_five": 0,
            "seconds_played": 0.0, "points": 0, "fg2m": 0, "fg2a": 0, "fg3m": 0,
            "fg3a": 0, "ftm": 0, "fta": 0, "reb_off": 0, "reb_def": 0,
            "reb_total": 0, "assists": 0, "steals": 0, "turnovers": 0,
            "blocks_favour": 0, "blocks_against": 0, "fouls_committed": 0,
            "fouls_received": 0, "plus_minus": 0, "valuation": 0}


class FakeSource(Source):
    name = "fake"

    def __init__(self, seasons, games_by_season, live_games=(), missing_pbp=()):
        self.seasons = seasons
        self.games_by_season = games_by_season
        self.live_games = set(live_games)
        self.missing_pbp = set(missing_pbp)
        self.boxscore_calls = []
        self.pbp_calls = []
        self.people_calls = []

    @property
    def requests_made(self):
        return len(self.boxscore_calls) + len(self.pbp_calls)

    def fetch_seasons(self):
        return FetchedList(raw_pages=[("0", b"{}")], rows=self.seasons)

    def fetch_games(self, season_code):
        return FetchedList(raw_pages=[(f"{season_code}:0", b"{}")],
                           rows=self.games_by_season.get(season_code, []))

    def fetch_people(self, season_code):
        self.people_calls.append(season_code)
        return FetchedList(raw_pages=[(f"{season_code}:0", b"{}")], rows=[])

    def fetch_boxscore(self, season_code, game_code, home, away):
        self.boxscore_calls.append((season_code, game_code))
        return FetchedGameDetail(raw=b"{}", rows=[box_row("001")], found=True)

    def fetch_pbp(self, season_code, game_code):
        self.pbp_calls.append((season_code, game_code))
        if (season_code, game_code) in self.missing_pbp:
            return FetchedGameDetail(raw=b"null", rows=[], found=False)
        return FetchedGameDetail(raw=b"{}", rows=[pbp_row(1)], found=True,
                                 live=(season_code, game_code) in self.live_games)


def two_season_source(**kw):
    return FakeSource(
        seasons=[season_row("E2026", 2026), season_row("E2025", 2025)],
        games_by_season={
            "E2026": [game_row("E2026", 1, played=0)],
            "E2025": [game_row("E2025", 1), game_row("E2025", 2), game_row("E2025", 3, played=0)],
        },
        **kw,
    )


def test_latest_skips_unplayed_season_and_finalizes(conn):
    src = two_season_source()
    stats = pipeline.run(conn, src, seasons="latest")
    assert stats.seasons_processed == ["E2025"]
    assert stats.games_processed == 2 and stats.games_finalized == 2
    assert src.boxscore_calls == [("E2025", 1), ("E2025", 2)]
    finals = {r["game_code"]: r["is_final"] for r in
              conn.execute("SELECT game_code, is_final FROM games WHERE season_code='E2025'")}
    assert finals == {1: 1, 2: 1, 3: 0}
    assert db.meta_get(conn, "last_successful_ingest_at")
    assert conn.execute("SELECT count(*) c FROM games").fetchone()["c"] == 4


def test_second_run_refetches_nothing_final(conn):
    src = two_season_source()
    pipeline.run(conn, src, seasons="latest")
    pipeline.run(conn, src, seasons="latest")
    assert len(src.boxscore_calls) == 2  # no re-fetch of final games
    assert len(src.people_calls) == 1    # weekly refresh, not per-run


def test_live_game_stays_pending(conn):
    src = two_season_source(live_games={("E2025", 2)})
    stats = pipeline.run(conn, src, seasons="latest")
    assert stats.games_finalized == 1
    row = conn.execute("SELECT is_final, pbp_status FROM games WHERE game_code=2 AND season_code='E2025'").fetchone()
    assert row["is_final"] == 0 and row["pbp_status"] == "ok"
    src.live_games = set()
    pipeline.run(conn, src, seasons="latest")
    assert src.boxscore_calls.count(("E2025", 2)) == 2
    assert src.boxscore_calls.count(("E2025", 1)) == 1


def test_missing_pbp_recorded_and_final(conn):
    src = two_season_source(missing_pbp={("E2025", 1), ("E2025", 2)})
    stats = pipeline.run(conn, src, seasons="latest")
    assert stats.pbp_missing == 2 and stats.games_finalized == 2
    assert not stats.errors
    rows = conn.execute("SELECT pbp_status, is_final FROM games WHERE played=1 AND season_code='E2025'").fetchall()
    assert all(r["pbp_status"] == "missing" and r["is_final"] == 1 for r in rows)
    assert conn.execute("SELECT count(*) c FROM pbp_events").fetchone()["c"] == 0


def test_all_processes_every_season_oldest_first(conn):
    src = two_season_source()
    stats = pipeline.run(conn, src, seasons="all")
    assert stats.seasons_processed == ["E2025", "E2026"]


def test_explicit_seasons_and_unknown_code(conn):
    src = two_season_source()
    stats = pipeline.run(conn, src, seasons="E2025")
    assert stats.seasons_processed == ["E2025"]
    import pytest
    with pytest.raises(ValueError, match="E1999"):
        pipeline.run(conn, src, seasons="E1999")


def test_limit_caps_detail_fetches(conn):
    src = two_season_source()
    stats = pipeline.run(conn, src, seasons="latest", limit=1)
    assert stats.games_processed == 1
    assert len(src.boxscore_calls) == 1
    pipeline.run(conn, src, seasons="latest")
    assert len(src.boxscore_calls) == 2


class FailingSource(FakeSource):
    def fetch_boxscore(self, season_code, game_code, home, away):
        self.boxscore_calls.append((season_code, game_code))
        raise RuntimeError("boom")


def test_consecutive_failures_abort_run(conn):
    games = {"E2025": [game_row("E2025", n) for n in range(1, 11)]}
    src = FailingSource(seasons=[season_row("E2025", 2025)], games_by_season=games)
    stats = pipeline.run(conn, src, seasons="latest")
    assert len(src.boxscore_calls) == pipeline.MAX_CONSECUTIVE_ERRORS
    assert any("aborted" in e for e in stats.errors)
    assert db.meta_get(conn, "last_successful_ingest_at") is None
    run = conn.execute("SELECT ok FROM ingest_runs").fetchone()
    assert run["ok"] == 0
