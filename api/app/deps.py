"""Shared router plumbing: season resolution and the cache/ETag response path."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, Response

from app import cache, queries
from app.db import SOURCE

CACHE_CONTROL = "public, max-age=300"


def resolve_season(conn, season: str | None) -> str:
    """No `season` means the newest season that has final games."""
    if season is None:
        latest = queries.latest_season(conn, SOURCE)
        if latest is None:
            raise HTTPException(503, "no ingested seasons yet — run the ingest job")
        return latest
    if not queries.season_exists(conn, SOURCE, season):
        raise HTTPException(404, f"season {season} not ingested")
    return season


def serve(request: Request, response: Response, conn, season: str,
          key: tuple, producer: Callable[[], Any]) -> Any:
    """Cache-aware response."""
    version = cache.season_version(conn, SOURCE, season)
    tag = cache.etag(key, version)
    headers = {"ETag": tag, "Cache-Control": CACHE_CONTROL, "X-Season": season}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    data = cache.get_or_compute(key, version, producer)
    response.headers.update(headers)
    return data
