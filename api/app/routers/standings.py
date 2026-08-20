"""Standings — page 1 of the site."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import Club, Phase, StandingsRow

router = APIRouter(prefix="/api", tags=["standings"])


@router.get("/clubs", response_model=list[Club])
def get_clubs(request: Request, response: Response,
              season: str | None = Query(None, description="season code, e.g. E2025"),
              conn: sqlite3.Connection = Depends(get_conn)):
    """Club names and crest URLs."""
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("clubs", season),
                 lambda: queries.clubs(conn, SOURCE, season))


@router.get("/standings", response_model=list[StandingsRow])
def get_standings(request: Request, response: Response,
                  season: str | None = Query(None, description="season code, e.g. E2025"),
                  phase: Phase | None = Query(None, description="FF for the Final Four placings"),
                  conn: sqlite3.Connection = Depends(get_conn)):
    """League table. Regular season by default; `phase=FF` gives the Final Four placings."""
    season = resolve_season(conn, season)
    if phase is Phase.FF:
        return serve(request, response, conn, season, ("standings-ff", season),
                     lambda: queries.final_four_table(conn, SOURCE, season))
    return serve(request, response, conn, season, ("standings", season),
                 lambda: queries.standings(conn, SOURCE, season))
