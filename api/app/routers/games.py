"""Games: schedule/results list, per-game detail, and the score worm."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import GameDetail, GameSummary, GameTimeline

router = APIRouter(prefix="/api", tags=["games"])


@router.get("/games", response_model=list[GameSummary])
def list_games(request: Request, response: Response,
               season: str | None = Query(None),
               round: int | None = Query(None, ge=1, description="filter by round"),
               club: str | None = Query(None, description="club code, home or away"),
               limit: int = Query(50, ge=1, le=500),
               offset: int = Query(0, ge=0),
               conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    key = ("games", season, round, club, limit, offset)
    return serve(request, response, conn, season, key,
                 lambda: queries.games(conn, SOURCE, season, round_=round, club=club,
                                       limit=limit, offset=offset))


@router.get("/games/{game_code}", response_model=GameDetail)
def get_game(request: Request, response: Response,
             game_code: int = Path(ge=1),
             season: str | None = Query(None),
             conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)

    def produce():
        detail = queries.game(conn, SOURCE, season, game_code)
        if detail is None:
            raise HTTPException(404, f"game {game_code} not found in {season}")
        return detail

    return serve(request, response, conn, season, ("game", season, game_code), produce)


@router.get("/games/{game_code}/timeline", response_model=GameTimeline)
def get_timeline(request: Request, response: Response,
                 game_code: int = Path(ge=1),
                 season: str | None = Query(None),
                 conn: sqlite3.Connection = Depends(get_conn)):
    """Score curve for the game chart.

    Rebuilt from pbp_events per request (see queries.game_timeline) rather than
    read from a table — the only computed endpoint today, and the pattern any
    future live-game endpoint will follow.
    """
    season = resolve_season(conn, season)

    def produce():
        tl = queries.game_timeline(conn, SOURCE, season, game_code)
        if tl is None:
            raise HTTPException(404, f"game {game_code} not found in {season}")
        return tl

    return serve(request, response, conn, season, ("timeline", season, game_code), produce)
