"""CLI: python -m metrics [--seasons latest|all|E2024,...] [--db PATH] [--validate]

Computes derived metrics tables from ingested data (no network). The nightly
CronJob chains it after ingest: python -m ingest && python -m metrics.

--validate skips recomputation and cross-checks stored metrics against the
official boxscore ground truth (valuation vs our PIR, plusMinus vs our
PBP-derived +/-, timePlayed vs our reconstructed seconds).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from ingest import db as ingest_db
from metrics import engine
from metrics.schema import ensure_schema

log = logging.getLogger("metrics")

SOURCE = "euroleague"


def resolve_seasons(conn, selector: str, source: str) -> list[str]:
    rows = conn.execute(
        """SELECT g.season_code FROM games g
           JOIN seasons s ON s.source = g.source AND s.code = g.season_code
           WHERE g.source = ? AND g.is_final = 1
           GROUP BY g.season_code ORDER BY s.year""",
        (source,),
    ).fetchall()
    available = [r["season_code"] for r in rows]
    if not available:
        raise SystemExit("no ingested seasons with final games — run ingest first")
    if selector == "latest":
        return [available[-1]]
    if selector == "all":
        return available
    requested = [c.strip() for c in selector.split(",") if c.strip()]
    unknown = set(requested) - set(available)
    if unknown:
        raise SystemExit(f"season(s) not ingested: {', '.join(sorted(unknown))}")
    return requested


def validate(conn, source: str, seasons: list[str]) -> int:
    """Cross-check computed metrics against official boxscore values."""
    worst_pir_mismatches = 0
    for season in seasons:
        row = conn.execute(
            """SELECT COUNT(*) n,
                      SUM(m.pir = b.valuation) pir_ok,
                      SUM(m.pm_computed IS NOT NULL) with_pbp,
                      SUM(m.pm_computed = b.plus_minus) pm_exact,
                      SUM(ABS(m.pm_computed - b.plus_minus) <= 2) pm_close,
                      SUM(ABS(m.seconds_computed - b.seconds_played) <= 60) sec_close
               FROM player_game_metrics m
               JOIN boxscore_lines b
                 ON b.source = m.source AND b.season_code = m.season_code
                AND b.game_code = m.game_code AND b.player_code = m.player_code
                AND b.entry_type = 'player'
               WHERE m.source = ? AND m.season_code = ?""",
            (source, season),
        ).fetchone()
        n, with_pbp = row["n"] or 0, row["with_pbp"] or 0
        if n == 0:
            print(f"{season}: no computed metrics — run without --validate first")
            continue
        pir_ok = row["pir_ok"] or 0
        worst_pir_mismatches += n - pir_ok
        print(f"{season}: {n} player-games")
        print(f"  PIR   == official valuation: {pir_ok}/{n} ({100.0 * pir_ok / n:.2f}%)")
        if with_pbp:
            pm_exact, pm_close = row["pm_exact"] or 0, row["pm_close"] or 0
            sec_close = row["sec_close"] or 0
            print(f"  +/-   == official plusMinus: {pm_exact}/{with_pbp} "
                  f"({100.0 * pm_exact / with_pbp:.2f}%), within ±2: "
                  f"{100.0 * pm_close / with_pbp:.2f}%")
            print(f"  court seconds within ±60s of timePlayed: "
                  f"{100.0 * sec_close / with_pbp:.2f}%")
        else:
            print("  (no PBP-based metrics this season)")
    return 1 if worst_pir_mismatches else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m metrics", description=__doc__)
    parser.add_argument("--seasons", default="latest",
                        help="'latest' (default), 'all', or comma-separated codes")
    parser.add_argument("--db", default=os.environ.get("ELCOURTSIDE_DB", "data/elcourtside.db"))
    parser.add_argument("--validate", action="store_true",
                        help="cross-check stored metrics against official boxscore values")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(message)s")

    conn = ingest_db.connect(args.db)
    ensure_schema(conn)
    try:
        seasons = resolve_seasons(conn, args.seasons, SOURCE)
        if args.validate:
            return validate(conn, SOURCE, seasons)
        for season in seasons:
            engine.compute_season(conn, SOURCE, season)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
