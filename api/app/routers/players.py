"""Players: PIR / +/- / clutch leaderboards and per-player detail."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import PlayerDetail, PlayerSeason, PlayerSort

router = APIRouter(prefix="/api", tags=["players"])


@router.get("/players", response_model=list[PlayerSeason])
def list_players(request: Request, response: Response,
                 season: str | None = Query(None),
                 sort: PlayerSort = Query(PlayerSort.pir_avg),
                 desc: bool = Query(True),
                 club: str | None = Query(None, description="club code"),
                 min_games: int = Query(0, ge=0, le=100),
                 limit: int = Query(50, ge=1, le=500),
                 offset: int = Query(0, ge=0),
                 conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    key = ("players", season, sort.value, desc, club, min_games, limit, offset)
    return serve(request, response, conn, season, key,
                 lambda: queries.players(conn, SOURCE, season, sort=sort.value, desc=desc,
                                         club=club, min_games=min_games,
                                         limit=limit, offset=offset))


@router.get("/players/{player_code}", response_model=PlayerDetail)
def get_player(request: Request, response: Response, player_code: str,
               season: str | None = Query(None),
               conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)

    def produce():
        detail = queries.player(conn, SOURCE, season, player_code)
        if detail is None:
            raise HTTPException(404, f"player {player_code} not found in {season}")
        return detail

    return serve(request, response, conn, season, ("player", season, player_code), produce)
