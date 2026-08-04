"""SQLite schema and storage helpers for the ingest pipeline.

Raw-first design: every API payload is stored zlib-compressed in
`raw_payloads` keyed by (source, kind, key), alongside the parsed tables.
A metrics bug or a new metric never requires re-hitting the API.

Idempotency model:
- seasons / games / people rows are upserted; re-ingesting is a no-op update.
- boxscore_lines / pbp_events are replaced per game inside a transaction
  (delete + insert), so re-fetching a game can never leave stale rows.
- games carries ingest bookkeeping (boxscore_status, pbp_status, is_final)
  that the schedule upsert never touches.
"""

from __future__ import annotations

import json
import sqlite3
import zlib
from collections.abc import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_payloads (
  source     TEXT NOT NULL,
  kind       TEXT NOT NULL,   -- seasons | games | boxscore | pbp | people
  key        TEXT NOT NULL,   -- e.g. '0', 'E2025:0', 'E2025:42'
  fetched_at TEXT NOT NULL,
  payload    BLOB NOT NULL,   -- zlib-compressed response body
  PRIMARY KEY (source, kind, key)
);

CREATE TABLE IF NOT EXISTS seasons (
  source           TEXT NOT NULL,
  code             TEXT NOT NULL,
  name             TEXT,
  alias            TEXT,
  year             INTEGER,
  start_date       TEXT,
  end_date         TEXT,
  winner_club_code TEXT,
  PRIMARY KEY (source, code)
);

CREATE TABLE IF NOT EXISTS games (
  source           TEXT NOT NULL,
  season_code      TEXT NOT NULL,
  game_code        INTEGER NOT NULL,
  identifier       TEXT,
  utc_date         TEXT,
  local_date       TEXT,
  round            INTEGER,
  round_name       TEXT,
  phase_type_code  TEXT,
  phase_type_name  TEXT,
  group_name       TEXT,
  played           INTEGER NOT NULL DEFAULT 0,
  game_status      TEXT,
  home_club_code   TEXT,
  home_club_name   TEXT,
  home_score       INTEGER,
  away_club_code   TEXT,
  away_club_name   TEXT,
  away_score       INTEGER,
  home_partials    TEXT,   -- JSON object as returned by the API
  away_partials    TEXT,
  winner_club_code TEXT,
  audience         INTEGER,
  -- ingest bookkeeping (never touched by the schedule upsert)
  boxscore_status  TEXT NOT NULL DEFAULT 'pending',  -- pending | ok | missing
  pbp_status       TEXT NOT NULL DEFAULT 'pending',  -- pending | ok | missing
  is_final         INTEGER NOT NULL DEFAULT 0,
  updated_at       TEXT,
  PRIMARY KEY (source, season_code, game_code)
);

CREATE TABLE IF NOT EXISTS boxscore_lines (
  source          TEXT NOT NULL,
  season_code     TEXT NOT NULL,
  game_code       INTEGER NOT NULL,
  is_home         INTEGER NOT NULL,          -- 1 = local side, 0 = road side
  entry_type      TEXT NOT NULL,             -- player | team | total
  player_code     TEXT NOT NULL DEFAULT '',  -- '' for team/total rows
  club_code       TEXT,
  player_name     TEXT,
  dorsal          TEXT,
  start_five      INTEGER,
  seconds_played  REAL,
  points          INTEGER,
  fg2m            INTEGER,
  fg2a            INTEGER,
  fg3m            INTEGER,
  fg3a            INTEGER,
  ftm             INTEGER,
  fta             INTEGER,
  reb_off         INTEGER,
  reb_def         INTEGER,
  reb_total       INTEGER,
  assists         INTEGER,
  steals          INTEGER,
  turnovers       INTEGER,
  blocks_favour   INTEGER,
  blocks_against  INTEGER,
  fouls_committed INTEGER,
  fouls_received  INTEGER,
  plus_minus      INTEGER,
  valuation       INTEGER,
  PRIMARY KEY (source, season_code, game_code, is_home, entry_type, player_code)
);

CREATE TABLE IF NOT EXISTS pbp_events (
  source      TEXT NOT NULL,
  season_code TEXT NOT NULL,
  game_code   INTEGER NOT NULL,
  quarter     INTEGER NOT NULL,   -- 1-4; 5 = all extra time (OT n via MINUTE)
  play_number INTEGER NOT NULL,
  play_type   TEXT,
  team_code   TEXT,
  player_code TEXT,               -- normalized: trimmed, 'P' prefix stripped
  player_name TEXT,
  dorsal      TEXT,
  minute      INTEGER,
  marker_time TEXT,
  points_a    INTEGER,
  points_b    INTEGER,
  play_info   TEXT,
  comment     TEXT,
  PRIMARY KEY (source, season_code, game_code, quarter, play_number)
);

CREATE TABLE IF NOT EXISTS people (
  source        TEXT NOT NULL,
  season_code   TEXT NOT NULL,
  person_code   TEXT NOT NULL,
  club_code     TEXT NOT NULL DEFAULT '',
  type_code     TEXT NOT NULL DEFAULT '',   -- J = player, E = coach, ...
  name          TEXT,
  type_name     TEXT,
  active        INTEGER,
  dorsal        TEXT,
  position      INTEGER,
  position_name TEXT,
  height        INTEGER,
  birth_date    TEXT,
  country_code  TEXT,
  start_date    TEXT,
  end_date      TEXT,
  PRIMARY KEY (source, season_code, person_code, club_code, type_code)
);

CREATE TABLE IF NOT EXISTS ingest_meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  seasons         TEXT,
  requests_made   INTEGER,
  games_processed INTEGER,
  errors          INTEGER,
  ok              INTEGER
);
"""


def connect(path: str, check_same_thread: bool = True) -> sqlite3.Connection:
    # check_same_thread=False is for the API tests, where one in-memory
    # database is shared with the TestClient's server thread.
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(SCHEMA)
    return conn


# -- raw payloads -------------------------------------------------------------

def store_raw(conn, source: str, kind: str, key: str, payload: bytes, fetched_at: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO raw_payloads (source, kind, key, fetched_at, payload)"
        " VALUES (?, ?, ?, ?, ?)",
        (source, kind, key, fetched_at, zlib.compress(payload)),
    )


def load_raw(conn, source: str, kind: str, key: str) -> bytes | None:
    row = conn.execute(
        "SELECT payload FROM raw_payloads WHERE source=? AND kind=? AND key=?",
        (source, kind, key),
    ).fetchone()
    return zlib.decompress(row["payload"]) if row else None


# -- upserts ------------------------------------------------------------------

def upsert_seasons(conn, source: str, rows: Iterable[dict]) -> None:
    conn.executemany(
        """INSERT INTO seasons (source, code, name, alias, year, start_date, end_date, winner_club_code)
           VALUES (:source, :code, :name, :alias, :year, :start_date, :end_date, :winner_club_code)
           ON CONFLICT (source, code) DO UPDATE SET
             name=excluded.name, alias=excluded.alias, year=excluded.year,
             start_date=excluded.start_date, end_date=excluded.end_date,
             winner_club_code=excluded.winner_club_code""",
        [{**r, "source": source} for r in rows],
    )


GAME_SCHEDULE_FIELDS = [
    "identifier", "utc_date", "local_date", "round", "round_name",
    "phase_type_code", "phase_type_name", "group_name", "played", "game_status",
    "home_club_code", "home_club_name", "home_score",
    "away_club_code", "away_club_name", "away_score",
    "home_partials", "away_partials", "winner_club_code", "audience",
]


def upsert_games(conn, source: str, rows: Iterable[dict], updated_at: str) -> None:
    cols = ["source", "season_code", "game_code", *GAME_SCHEDULE_FIELDS, "updated_at"]
    updates = ", ".join(f"{f}=excluded.{f}" for f in [*GAME_SCHEDULE_FIELDS, "updated_at"])
    conn.executemany(
        f"""INSERT INTO games ({", ".join(cols)})
            VALUES ({", ".join(":" + c for c in cols)})
            ON CONFLICT (source, season_code, game_code) DO UPDATE SET {updates}""",
        [{**r, "source": source, "updated_at": updated_at} for r in rows],
    )


def set_game_ingest_state(conn, source: str, season_code: str, game_code: int,
                          boxscore_status: str, pbp_status: str, is_final: int,
                          updated_at: str) -> None:
    conn.execute(
        """UPDATE games SET boxscore_status=?, pbp_status=?, is_final=?, updated_at=?
           WHERE source=? AND season_code=? AND game_code=?""",
        (boxscore_status, pbp_status, is_final, updated_at, source, season_code, game_code),
    )


BOXSCORE_FIELDS = [
    "is_home", "entry_type", "player_code", "club_code", "player_name", "dorsal",
    "start_five", "seconds_played", "points", "fg2m", "fg2a", "fg3m", "fg3a",
    "ftm", "fta", "reb_off", "reb_def", "reb_total", "assists", "steals",
    "turnovers", "blocks_favour", "blocks_against", "fouls_committed",
    "fouls_received", "plus_minus", "valuation",
]


def replace_boxscore_lines(conn, source: str, season_code: str, game_code: int,
                           rows: Iterable[dict]) -> None:
    conn.execute(
        "DELETE FROM boxscore_lines WHERE source=? AND season_code=? AND game_code=?",
        (source, season_code, game_code),
    )
    cols = ["source", "season_code", "game_code", *BOXSCORE_FIELDS]
    conn.executemany(
        f"INSERT INTO boxscore_lines ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
        [{**r, "source": source, "season_code": season_code, "game_code": game_code} for r in rows],
    )


PBP_FIELDS = [
    "quarter", "play_number", "play_type", "team_code", "player_code",
    "player_name", "dorsal", "minute", "marker_time", "points_a", "points_b",
    "play_info", "comment",
]


def replace_pbp_events(conn, source: str, season_code: str, game_code: int,
                       rows: Iterable[dict]) -> None:
    conn.execute(
        "DELETE FROM pbp_events WHERE source=? AND season_code=? AND game_code=?",
        (source, season_code, game_code),
    )
    cols = ["source", "season_code", "game_code", *PBP_FIELDS]
    conn.executemany(
        f"INSERT OR REPLACE INTO pbp_events ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
        [{**r, "source": source, "season_code": season_code, "game_code": game_code} for r in rows],
    )


PEOPLE_FIELDS = [
    "person_code", "club_code", "type_code", "name", "type_name", "active",
    "dorsal", "position", "position_name", "height", "birth_date",
    "country_code", "start_date", "end_date",
]


def upsert_people(conn, source: str, season_code: str, rows: Iterable[dict]) -> None:
    cols = ["source", "season_code", *PEOPLE_FIELDS]
    conn.executemany(
        f"INSERT OR REPLACE INTO people ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
        [{**r, "source": source, "season_code": season_code} for r in rows],
    )


# -- meta / runs --------------------------------------------------------------

def meta_get(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM ingest_meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def meta_set(conn, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO ingest_meta (key, value) VALUES (?, ?)", (key, value))


def start_run(conn, started_at: str, seasons: str) -> int:
    cur = conn.execute(
        "INSERT INTO ingest_runs (started_at, seasons) VALUES (?, ?)", (started_at, seasons)
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id: int, finished_at: str, requests_made: int,
               games_processed: int, errors: int) -> None:
    conn.execute(
        """UPDATE ingest_runs SET finished_at=?, requests_made=?, games_processed=?,
           errors=?, ok=? WHERE id=?""",
        (finished_at, requests_made, games_processed, errors, 0 if errors else 1, run_id),
    )
    conn.commit()
