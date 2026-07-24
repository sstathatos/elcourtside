from ingest import db


def _game(code=1, **over):
    row = {
        "season_code": "E2025", "game_code": code, "identifier": f"E2025_{code}",
        "utc_date": "2025-10-01T18:00:00Z", "local_date": "2025-10-01T20:00:00",
        "round": 1, "round_name": "Round 1", "phase_type_code": "RS",
        "phase_type_name": "Regular Season", "group_name": "", "played": 1,
        "game_status": "Confirmed", "home_club_code": "OLY", "home_club_name": "Olympiacos",
        "home_score": 80, "away_club_code": "MAD", "away_club_name": "Real Madrid",
        "away_score": 75, "home_partials": None, "away_partials": None,
        "winner_club_code": "OLY", "audience": 10000,
    }
    row.update(over)
    return row


def test_upsert_games_idempotent_and_updates(conn):
    db.upsert_games(conn, "test", [_game()], "t1")
    db.upsert_games(conn, "test", [_game(home_score=82)], "t2")
    rows = conn.execute("SELECT * FROM games").fetchall()
    assert len(rows) == 1
    assert rows[0]["home_score"] == 82
    assert rows[0]["updated_at"] == "t2"


def test_upsert_games_preserves_ingest_state(conn):
    db.upsert_games(conn, "test", [_game()], "t1")
    db.set_game_ingest_state(conn, "test", "E2025", 1, "ok", "missing", 1, "t2")
    db.upsert_games(conn, "test", [_game(audience=11000)], "t3")  # schedule refresh
    row = conn.execute("SELECT * FROM games").fetchone()
    assert row["boxscore_status"] == "ok"
    assert row["pbp_status"] == "missing"
    assert row["is_final"] == 1
    assert row["audience"] == 11000


def test_raw_roundtrip(conn):
    payload = b'{"data": [1, 2, 3]}'
    db.store_raw(conn, "test", "games", "E2025:0", payload, "t1")
    assert db.load_raw(conn, "test", "games", "E2025:0") == payload
    # stored compressed, refetch replaces
    db.store_raw(conn, "test", "games", "E2025:0", b"{}", "t2")
    assert db.load_raw(conn, "test", "games", "E2025:0") == b"{}"
    assert db.load_raw(conn, "test", "games", "nope") is None


def _box_row(player_code="001", **over):
    row = {
        "is_home": 1, "entry_type": "player", "player_code": player_code,
        "club_code": "OLY", "player_name": "X", "dorsal": "7", "start_five": 1,
        "seconds_played": 1200.0, "points": 10, "fg2m": 2, "fg2a": 4, "fg3m": 1,
        "fg3a": 3, "ftm": 3, "fta": 4, "reb_off": 1, "reb_def": 4, "reb_total": 5,
        "assists": 2, "steals": 1, "turnovers": 2, "blocks_favour": 0,
        "blocks_against": 0, "fouls_committed": 3, "fouls_received": 4,
        "plus_minus": 6, "valuation": 15,
    }
    row.update(over)
    return row


def test_replace_boxscore_idempotent(conn):
    rows = [_box_row("001"), _box_row("002"), _box_row("", entry_type="total")]
    db.replace_boxscore_lines(conn, "test", "E2025", 1, rows)
    db.replace_boxscore_lines(conn, "test", "E2025", 1, rows)
    assert conn.execute("SELECT count(*) c FROM boxscore_lines").fetchone()["c"] == 3
    # re-ingest with fewer rows leaves no stale rows behind
    db.replace_boxscore_lines(conn, "test", "E2025", 1, rows[:1])
    assert conn.execute("SELECT count(*) c FROM boxscore_lines").fetchone()["c"] == 1


def test_replace_pbp_idempotent(conn):
    rows = [
        {"quarter": 1, "play_number": 2, "play_type": "BP", "team_code": "",
         "player_code": "", "player_name": None, "dorsal": None, "minute": 1,
         "marker_time": "", "points_a": None, "points_b": None,
         "play_info": "Begin Period", "comment": ""},
        {"quarter": 1, "play_number": 5, "play_type": "AS", "team_code": "IST",
         "player_code": "007200", "player_name": "LARKIN, SHANE", "dorsal": "0",
         "minute": 1, "marker_time": "09:36", "points_a": None, "points_b": None,
         "play_info": "Assist (1)", "comment": ""},
    ]
    db.replace_pbp_events(conn, "test", "E2025", 1, rows)
    db.replace_pbp_events(conn, "test", "E2025", 1, rows)
    assert conn.execute("SELECT count(*) c FROM pbp_events").fetchone()["c"] == 2


def test_meta(conn):
    assert db.meta_get(conn, "k") is None
    db.meta_set(conn, "k", "v1")
    db.meta_set(conn, "k", "v2")
    assert db.meta_get(conn, "k") == "v2"


def test_runs(conn):
    run_id = db.start_run(conn, "t1", "latest")
    db.finish_run(conn, run_id, "t2", requests_made=10, games_processed=3, errors=0)
    row = conn.execute("SELECT * FROM ingest_runs").fetchone()
    assert row["ok"] == 1 and row["requests_made"] == 10
