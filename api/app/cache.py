"""In-process response cache, versioned by when the data was computed."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

MAX_ENTRIES = 512
_STAMP_TTL = 5.0  # seconds to reuse a computed_at lookup across a burst

SCHEMA_VERSION = "4"

_entries: OrderedDict[tuple, Any] = OrderedDict()
_stamps: dict[tuple[str, str], tuple[float, str]] = {}
_lock = threading.Lock()

hits = 0
misses = 0


def season_version(conn, source: str, season_code: str) -> str:
    """The season's computed_at stamp — the cache key's version component."""
    now = time.monotonic()
    cached = _stamps.get((source, season_code))
    if cached and now - cached[0] < _STAMP_TTL:
        return cached[1]
    row = conn.execute(
        "SELECT value FROM metrics_meta WHERE key = ?",
        (f"computed_at:{source}:{season_code}",),
    ).fetchone()
    stamp = row["value"] if row else "unknown"
    _stamps[(source, season_code)] = (now, stamp)
    return stamp


def ttl_version(seconds: int) -> str:
    """Time-bucketed version for data with no computed_at (live games)."""
    return f"ttl:{int(time.time() // seconds)}"


def get_or_compute(key: tuple, version: str, producer: Callable[[], Any]) -> Any:
    global hits, misses
    full_key = (*key, version, SCHEMA_VERSION)
    with _lock:
        if full_key in _entries:
            _entries.move_to_end(full_key)
            hits += 1
            return _entries[full_key]
    value = producer()          # computed outside the lock: SQLite is fine
    with _lock:                 # concurrently, and a slow query must not
        _entries[full_key] = value   # block cache reads for other routes
        _entries.move_to_end(full_key)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)
        misses += 1
    return value


def etag(key: tuple, version: str) -> str:
    """Weak-ish validator: same route+params+data version+shape → same tag."""
    raw = repr((*key, version, SCHEMA_VERSION)).encode()
    return '"' + hashlib.sha256(raw).hexdigest()[:32] + '"'


def clear() -> None:
    with _lock:
        _entries.clear()
        _stamps.clear()


def stats() -> dict[str, int]:
    return {"entries": len(_entries), "hits": hits, "misses": misses}
