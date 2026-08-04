"""Standings — page 1 of the site. Straight read of the `standings` table,
which the metrics engine already ranked with the Euroleague tiebreak chain.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import StandingsRow

router = APIRouter(prefix="/api", tags=["standings"])


@router.get("/standings", response_model=list[StandingsRow])
def get_standings(request: Request, response: Response,
                  season: str | None = Query(None, description="season code, e.g. E2025"),
                  conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("standings", season),
                 lambda: queries.standings(conn, SOURCE, season))
