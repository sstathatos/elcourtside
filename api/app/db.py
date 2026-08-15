"""Read-only SQLite access for the API."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator

SOURCE = "euroleague"


def db_path() -> str:
    """Same default as the ingest/metrics CLIs, so all three agree."""
    return os.environ.get("ELCOURTSIDE_DB", "data/elcourtside.db")


def connect_ro(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path or db_path()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency. Tests override this with an in-memory database."""
    conn = connect_ro()
    try:
        yield conn
    finally:
        conn.close()
