"""Cluster-internal endpoints. Never routed through the public ingress.

`/internal/backup.sqlite` exists because the DB lives on a node-local PVC: a
backup pod scheduled on the *other* node cannot mount that volume, so it pulls
a snapshot over HTTP instead. `VACUUM INTO` writes a consistent copy even while
the ingest CronJob is mid-transaction — copying the file (and its WAL) by hand
could capture a torn state.
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import sqlite3
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app import queries
from app.db import get_conn

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)

TOKEN_ENV = "ELCOURTSIDE_INTERNAL_TOKEN"


def _authorize(request: Request) -> None:
    """Token when one is configured; otherwise private-network callers only.

    In the cluster the backup CronJob holds the token from a Secret. Locally
    the env var is unset and loopback calls just work, which keeps development
    friction at zero without opening anything up in prod.
    """
    token = os.environ.get(TOKEN_ENV)
    if token:
        if request.headers.get("x-internal-token") != token:
            raise HTTPException(403, "internal endpoint")
        return
    host = request.client.host if request.client else ""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        raise HTTPException(403, "internal endpoint") from None
    if not (addr.is_private or addr.is_loopback):
        raise HTTPException(403, "internal endpoint")


@router.get("/backup.sqlite")
def backup(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    _authorize(request)
    tmpdir = tempfile.mkdtemp(prefix="elcourtside-backup-")
    dest = os.path.join(tmpdir, "elcourtside.sqlite")
    try:
        queries.sqlite_backup(conn, dest)
    except sqlite3.Error as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(500, f"backup failed: {exc}") from exc
    return FileResponse(
        dest,
        media_type="application/vnd.sqlite3",
        filename="elcourtside.sqlite",
        background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
    )
