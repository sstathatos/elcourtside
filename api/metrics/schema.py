"""Derived metrics tables — same SQLite file as ingest, own DDL block."""

ENGINE_VERSION = 3  # + team shooting/rebounding and opponent totals

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_game_metrics (
  source          TEXT NOT NULL,
  season_code     TEXT NOT NULL,
  game_code       INTEGER NOT NULL,
  player_code     TEXT NOT NULL,
  club_code       TEXT,
  is_home         INTEGER,
  pir             INTEGER,   -- our PIR from the boxscore line
  pm_computed     INTEGER,   -- +/- reconstructed from PBP; NULL when no PBP
  seconds_computed REAL,     -- on-court seconds from PBP; NULL when no PBP
  poss_share      REAL,      -- team possessions x minutes share
  fouls_drawn     INTEGER,
  clutch_seconds  REAL,
  clutch_points   INTEGER,
  clutch_pm       INTEGER,
  opp_fgm         INTEGER,
  opp_fga         INTEGER,
  opp_points      INTEGER,
  PRIMARY KEY (source, season_code, game_code, player_code)
);

CREATE TABLE IF NOT EXISTS team_game_metrics (
  source           TEXT NOT NULL,
  season_code      TEXT NOT NULL,
  game_code        INTEGER NOT NULL,
  club_code        TEXT NOT NULL,
  is_home          INTEGER,
  points           INTEGER,
  possessions      REAL,
  fouls_drawn      INTEGER,
  max_run          INTEGER,
  max_run_detail   TEXT,      -- JSON {points, start_s, end_s}
  max_lead         INTEGER,
  lost             INTEGER,   -- 1 = this club lost the game
  clutch_pts_for   INTEGER,
  clutch_pts_against INTEGER,
  clutch_pm        INTEGER,
  clutch_seconds   REAL,
  lineup_anomalies INTEGER,
  PRIMARY KEY (source, season_code, game_code, club_code)
);

CREATE TABLE IF NOT EXISTS player_season_metrics (
  source            TEXT NOT NULL,
  season_code       TEXT NOT NULL,
  player_code       TEXT NOT NULL,
  player_name       TEXT,
  clubs             TEXT,     -- comma-separated distinct clubs (transfers)
  games_played      INTEGER,  -- games with seconds > 0
  seconds           REAL,
  points            INTEGER,
  reb_total         INTEGER,
  assists           INTEGER,
  steals            INTEGER,
  blocks_favour     INTEGER,
  turnovers         INTEGER,
  fouls_drawn       INTEGER,
  pir_total         INTEGER,
  pir_avg           REAL,
  pir_per36         REAL,
  pm_total          INTEGER,
  pm_per36          REAL,
  clutch_seconds    REAL,
  clutch_points     INTEGER,
  clutch_pm         INTEGER,
  fouls_drawn_per100 REAL,   -- per 100 possessions available while on court
  reb_off           INTEGER,
  reb_def           INTEGER,
  fg2m              INTEGER,
  fg2a              INTEGER,
  fg3m              INTEGER,
  fg3a              INTEGER,
  ftm               INTEGER,
  fta               INTEGER,
  opp_fgm           INTEGER,
  opp_fga           INTEGER,
  opp_points        INTEGER,
  poss_share        REAL,     -- minutes-weighted possessions; denominator for TOV/100 and DRTG
  PRIMARY KEY (source, season_code, player_code)
);

CREATE TABLE IF NOT EXISTS team_season_metrics (
  source              TEXT NOT NULL,
  season_code         TEXT NOT NULL,
  club_code           TEXT NOT NULL,
  games               INTEGER,
  possessions_avg     REAL,
  fouls_drawn_per100  REAL,
  max_run             INTEGER,
  max_run_game        INTEGER,
  max_blown_lead      INTEGER,
  max_blown_lead_game INTEGER,
  clutch_pts_for      INTEGER,
  clutch_pts_against  INTEGER,
  clutch_seconds      REAL,
  points              INTEGER,
  fg2m                INTEGER,
  fg2a                INTEGER,
  fg3m                INTEGER,
  fg3a                INTEGER,
  ftm                 INTEGER,
  fta                 INTEGER,
  reb_off             INTEGER,
  reb_def             INTEGER,
  assists             INTEGER,
  steals              INTEGER,
  blocks_favour       INTEGER,
  turnovers           INTEGER,
  possessions         REAL,
  opp_points          INTEGER,
  opp_fg2m            INTEGER,
  opp_fg2a            INTEGER,
  opp_fg3m            INTEGER,
  opp_fg3a            INTEGER,
  opp_ftm             INTEGER,
  opp_fta             INTEGER,
  opp_reb_off         INTEGER,
  opp_reb_def         INTEGER,
  opp_turnovers       INTEGER,
  opp_possessions     REAL,
  PRIMARY KEY (source, season_code, club_code)
);

CREATE TABLE IF NOT EXISTS standings (
  source          TEXT NOT NULL,
  season_code     TEXT NOT NULL,
  club_code       TEXT NOT NULL,
  club_name       TEXT,
  games           INTEGER,
  wins            INTEGER,
  losses          INTEGER,
  points_for      INTEGER,
  points_against  INTEGER,
  point_diff      INTEGER,
  rank            INTEGER,
  PRIMARY KEY (source, season_code, club_code)
);

CREATE TABLE IF NOT EXISTS metrics_meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
"""


_ADDED_COLUMNS = {
    "player_game_metrics": [
        ("opp_fgm", "INTEGER"), ("opp_fga", "INTEGER"), ("opp_points", "INTEGER"),
    ],
    "team_season_metrics": [
        ("points", "INTEGER"), ("fg2m", "INTEGER"), ("fg2a", "INTEGER"),
        ("fg3m", "INTEGER"), ("fg3a", "INTEGER"), ("ftm", "INTEGER"),
        ("fta", "INTEGER"), ("reb_off", "INTEGER"), ("reb_def", "INTEGER"),
        ("assists", "INTEGER"), ("steals", "INTEGER"),
        ("blocks_favour", "INTEGER"), ("turnovers", "INTEGER"),
        ("possessions", "REAL"),
        ("opp_points", "INTEGER"), ("opp_fg2m", "INTEGER"), ("opp_fg2a", "INTEGER"),
        ("opp_fg3m", "INTEGER"), ("opp_fg3a", "INTEGER"), ("opp_ftm", "INTEGER"),
        ("opp_fta", "INTEGER"), ("opp_reb_off", "INTEGER"),
        ("opp_reb_def", "INTEGER"), ("opp_turnovers", "INTEGER"),
        ("opp_possessions", "REAL"),
    ],
    "player_season_metrics": [
        ("reb_off", "INTEGER"), ("reb_def", "INTEGER"),
        ("fg2m", "INTEGER"), ("fg2a", "INTEGER"),
        ("fg3m", "INTEGER"), ("fg3a", "INTEGER"),
        ("ftm", "INTEGER"), ("fta", "INTEGER"),
        ("opp_fgm", "INTEGER"), ("opp_fga", "INTEGER"), ("opp_points", "INTEGER"),
        ("poss_share", "REAL"),
    ],
}


def migrate(conn) -> None:
    for table, columns in _ADDED_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def ensure_schema(conn) -> None:
    conn.executescript(SCHEMA)
    migrate(conn)
