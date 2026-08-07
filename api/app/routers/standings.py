"""Standings — page 1 of the site. Straight read of the `standings` table,
which the metrics engine already ranked with the Euroleague tiebreak chain.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import Club, StandingsRow

router = APIRouter(prefix="/api", tags=["standings"])


@router.get("/clubs", response_model=list[Club])
def get_clubs(request: Request, response: Response,
              season: str | None = Query(None, description="season code, e.g. E2025"),
              conn: sqlite3.Connection = Depends(get_conn)):
    """Club names and crest URLs. The UI fetches this once and resolves crests
    by club code, so every other endpoint stays free of image URLs."""
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("clubs", season),
                 lambda: queries.clubs(conn, SOURCE, season))


@router.get("/standings", response_model=list[StandingsRow])
def get_standings(request: Request, response: Response,
                  season: str | None = Query(None, description="season code, e.g. E2025"),
                  conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("standings", season),
                 lambda: queries.standings(conn, SOURCE, season))
