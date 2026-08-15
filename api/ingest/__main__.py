"""CLI entrypoint: python -m ingest [--seasons latest|all|E2024,E2025] ..."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ingest import db, pipeline
from ingest.client import PoliteClient
from ingest.sources import SOURCES, create_source

MIN_POLITE_INTERVAL = 2.0  # seconds between requests; see doc/plan.md

log = logging.getLogger("ingest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingest", description=__doc__)
    parser.add_argument("--seasons", default="latest",
                        help="'latest' (default), 'all', or comma-separated codes like E2024,E2025")
    parser.add_argument("--db", default=os.environ.get("ELCOURTSIDE_DB", "data/elcourtside.db"),
                        help="SQLite path (default: $ELCOURTSIDE_DB or data/elcourtside.db)")
    parser.add_argument("--source", default="euroleague", choices=sorted(SOURCES))
    parser.add_argument("--limit", type=int, default=None,
                        help="max games to detail-fetch this run (dev/testing)")
    parser.add_argument("--min-interval", type=float, default=MIN_POLITE_INTERVAL,
                        help=f"seconds between API requests (floor: {MIN_POLITE_INTERVAL})")
    parser.add_argument("--reparse", action="store_true",
                        help="re-parse boxscore/pbp from stored raw payloads (no network)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(message)s")

    if args.reparse:
        from ingest import reparse
        conn = db.connect(args.db)
        try:
            seasons = reparse.resolve_db_seasons(conn, args.source, args.seasons)
            counts = reparse.reparse_registries(conn, args.source, seasons)
            counts |= reparse.reparse_details(conn, args.source, seasons)
        finally:
            conn.close()
        log.info("reparsed: %s", counts)
        return 0

    min_interval = args.min_interval
    if min_interval < MIN_POLITE_INTERVAL:
        log.warning("--min-interval %.1fs below politeness floor, using %.1fs",
                    min_interval, MIN_POLITE_INTERVAL)
        min_interval = MIN_POLITE_INTERVAL

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(args.db)
    client = PoliteClient(min_interval=min_interval)
    source = create_source(args.source, client)

    try:
        stats = pipeline.run(conn, source, seasons=args.seasons, limit=args.limit)
    finally:
        client.close()
        conn.close()

    log.info("done: seasons=%s games=%d finalized=%d boxscore_missing=%d "
             "pbp_missing=%d requests=%d errors=%d",
             ",".join(stats.seasons_processed) or "-", stats.games_processed,
             stats.games_finalized, stats.boxscores_missing, stats.pbp_missing,
             stats.requests_made, len(stats.errors))
    for err in stats.errors[:20]:
        log.error("error: %s", err)
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
