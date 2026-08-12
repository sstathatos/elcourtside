"""FastAPI application: routes, /health, and Prometheus /metrics.

Run locally:  .venv/bin/uvicorn app.main:app --reload
In the cluster the same image runs `python -m ingest` as a CronJob, so the API
and the pipeline never drift apart.
"""

from __future__ import annotations

import logging
import os
import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily
from prometheus_fastapi_instrumentator import Instrumentator

from app import cache, queries
from app.db import SOURCE, connect_ro, db_path
from app.models import Health
from app.routers import games, indexes, internal, players, seasons, standings, teams

log = logging.getLogger("api")

DESCRIPTION = """
Euroleague statistics served from a locally ingested dataset — standings,
games, teams, players, and the play-by-play-derived indexes (clutch, scoring
runs, blown leads, fouls drawn per possession).

Every value is precomputed nightly by `python -m metrics`; responses carry an
ETag tied to that computation, so `If-None-Match` gets you a 304 until the
data actually changes.
"""


class PipelineCollector:
    """Exports ingest/metrics health read straight from the database.

    CronJob pods live for minutes and would be missed by a 30 s scrape, so the
    always-on API reports on the pipeline's behalf.
    """

    def collect(self):
        try:
            conn = connect_ro()
        except sqlite3.Error:
            return
        try:
            values = queries.gauges(conn, SOURCE)
        except sqlite3.Error:
            return
        finally:
            conn.close()
        descriptions = {
            "games_ingested": "Final games stored in the database",
            "games_missing_pbp": "Final games with no play-by-play (pre-2007 era)",
            "last_successful_ingest_timestamp": "Unix time of the last successful ingest run",
            "metrics_computed_at_timestamp": "Unix time of the most recent metrics computation",
        }
        for name, value in values.items():
            yield GaugeMetricFamily(f"elcourtside_{name}",
                                    descriptions.get(name, name), value=value)


def create_app() -> FastAPI:
    app = FastAPI(
        title="elcourtside API",
        description=DESCRIPTION,
        version="0.1.0",
        # Under /api like every route, so the Ingress needs one path rule and
        # the footer's "API docs" link resolves the same locally and in the
        # cluster. /health and /metrics stay at the root: probes and the
        # ServiceMonitor address the pod directly, never through the Ingress.
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    origins = os.environ.get("ELCOURTSIDE_CORS_ORIGINS", "http://localhost:4321")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    for module in (seasons, standings, games, teams, players, indexes, internal):
        app.include_router(module.router)

    @app.get("/health", response_model=Health, tags=["ops"])
    def health():
        """Liveness + a cheap read of the database the container is serving."""
        try:
            conn = connect_ro()
            try:
                n = len(queries.list_seasons(conn, SOURCE))
            finally:
                conn.close()
            status, db_state = "ok", "readable"
        except sqlite3.Error as exc:
            log.warning("health: database unreadable: %s", exc)
            n, status, db_state = 0, "degraded", "unreadable"
        return {"status": status, "database": db_state, "seasons": n,
                "cache": cache.stats()}

    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    try:
        REGISTRY.register(PipelineCollector())
    except ValueError:  # already registered (reload / second app in-process)
        pass
    return app


app = create_app()
