"""Season list — drives the season picker and the boxscore-only era label."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from app import cache, queries
from app.db import SOURCE, get_conn
from app.deps import CACHE_CONTROL
from app.models import Season

router = APIRouter(prefix="/api", tags=["seasons"])


@router.get("/seasons", response_model=list[Season])
def list_seasons(request: Request, response: Response,
                 conn: sqlite3.Connection = Depends(get_conn)):
    # Versioned across *all* seasons: the newest season's stamp alone left an
    # older season invisible after it was ingested, because adding it never
    # touched that stamp.
    version = queries.seasons_version(conn, SOURCE)
    key = ("seasons",)
    tag = cache.etag(key, version)
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers={"ETag": tag, "Cache-Control": CACHE_CONTROL})
    data = cache.get_or_compute(key, version, lambda: queries.list_seasons(conn, SOURCE))
    response.headers["ETag"] = tag
    response.headers["Cache-Control"] = CACHE_CONTROL
    return data
