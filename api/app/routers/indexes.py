"""Indexes — the metrics that exist nowhere else pre-computed: scoring runs,
blown leads, clutch, fouls drawn per 100 possessions.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, Request, Response

from app import queries
from app.db import SOURCE, get_conn
from app.deps import resolve_season, serve
from app.models import BlownLeadRow, ClutchIndex, FoulsDrawnIndex, RunRow

router = APIRouter(prefix="/api/indexes", tags=["indexes"])


@router.get("/runs", response_model=list[RunRow])
def biggest_runs(request: Request, response: Response,
                 season: str | None = Query(None),
                 limit: int = Query(25, ge=1, le=200),
                 conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("runs", season, limit),
                 lambda: queries.index_runs(conn, SOURCE, season, limit))


@router.get("/blown-leads", response_model=list[BlownLeadRow])
def blown_leads(request: Request, response: Response,
                season: str | None = Query(None),
                limit: int = Query(25, ge=1, le=200),
                conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("blown-leads", season, limit),
                 lambda: queries.index_blown_leads(conn, SOURCE, season, limit))


@router.get("/clutch", response_model=ClutchIndex)
def clutch(request: Request, response: Response,
           season: str | None = Query(None),
           limit: int = Query(25, ge=1, le=200),
           conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    return serve(request, response, conn, season, ("clutch", season, limit),
                 lambda: queries.index_clutch(conn, SOURCE, season, limit))


@router.get("/fouls-drawn", response_model=FoulsDrawnIndex)
def fouls_drawn(request: Request, response: Response,
                season: str | None = Query(None),
                limit: int = Query(25, ge=1, le=200),
                min_games: int = Query(5, ge=0, le=100),
                conn: sqlite3.Connection = Depends(get_conn)):
    season = resolve_season(conn, season)
    key = ("fouls-drawn", season, limit, min_games)
    return serve(request, response, conn, season, key,
                 lambda: queries.index_fouls_drawn(conn, SOURCE, season, limit, min_games))
