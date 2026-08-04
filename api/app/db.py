"""Read-only SQLite access for the API.

The ingest CronJob is the only writer; the API never mutates a row. Opening
the file with `mode=ro` makes that a guarantee the database enforces rather
than a convention. WAL (set by the writer in ingest.db.connect) lets readers
run while a nightly ingest is mid-transaction, so no request ever blocks on
the pipeline.

Connections are per-request and cheap (sqlite3.connect is a file open, not a
network handshake); a module-level connection would be shared across threads
and is exactly the pattern SQLite dislikes.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator

SOURCE = "euroleague"


def db_path() -> str:
    """Same default as the ingest/metrics CLIs, so all three agree."""
    return os.environ.get("ELCOURTSIDE_DB", "data/elcourtside.db")


def connect_ro(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path or db_path()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency. Tests override this with an in-memory database."""
    conn = connect_ro()
    try:
        yield conn
    finally:
        conn.close()
