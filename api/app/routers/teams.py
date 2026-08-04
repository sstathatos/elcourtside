"""Teams: season table and per-club detail with a game log."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import TeamDetail, TeamSeason, TeamSort

router = APIRouter(prefix="/api", tags=["teams"])


@router.get("/teams", response_model=list[TeamSeason])
def list_teams(request: Request, response: Response,
               season: str | None = Query(None),
               sort: TeamSort = Query(TeamSort.max_run),
               desc: bool = Query(True),
               conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    key = ("teams", season, sort.value, desc)
    return serve(request, response, conn, season, key,
                 lambda: queries.teams(conn, SOURCE, season, sort=sort.value, desc=desc))


@router.get("/teams/{club_code}", response_model=TeamDetail)
def get_team(request: Request, response: Response, club_code: str,
             season: str | None = Query(None),
             conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)

    def produce():
        detail = queries.team(conn, SOURCE, season, club_code)
        if detail is None:
            raise HTTPException(404, f"club {club_code} not found in {season}")
        return detail

    return serve(request, response, conn, season, ("team", season, club_code), produce)
