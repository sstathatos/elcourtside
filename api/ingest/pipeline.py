"""Ingest orchestration: backfill and nightly incremental are the same code — "fetch details for played, non-final games" — only season selection differs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ingest import db
from ingest.sources.base import Source

log = logging.getLogger("ingest")

PEOPLE_REFRESH = timedelta(days=7)
MAX_CONSECUTIVE_ERRORS = 5


@dataclass
class RunStats:
    seasons_processed: list[str] = field(default_factory=list)
    games_processed: int = 0
    games_finalized: int = 0
    boxscores_missing: int = 0
    pbp_missing: int = 0
    requests_made: int = 0
    errors: list[str] = field(default_factory=list)


class AbortRun(Exception):
    """Too many consecutive failures — stop instead of hammering the API."""


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).isoformat(timespec="seconds")


def run(conn, source: Source, seasons: str = "latest",
        limit: int | None = None, now: datetime | None = None) -> RunStats:
    stats = RunStats()
    started_at = _now_iso(now)
    run_id = db.start_run(conn, started_at, seasons)

    fetched = source.fetch_seasons()
    for key, raw in fetched.raw_pages:
        db.store_raw(conn, source.name, "seasons", key, raw, started_at)
    db.upsert_seasons(conn, source.name, fetched.rows)
    conn.commit()

    by_year_desc = [s["code"] for s in sorted(fetched.rows, key=lambda s: s["year"] or 0, reverse=True)]
    if seasons == "latest":
        candidates, newest_played_only = by_year_desc, True
    elif seasons == "all":
        candidates, newest_played_only = list(reversed(by_year_desc)), False
    else:
        requested = [c.strip() for c in seasons.split(",") if c.strip()]
        unknown = set(requested) - set(by_year_desc)
        if unknown:
            raise ValueError(f"unknown season code(s): {', '.join(sorted(unknown))}")
        candidates, newest_played_only = requested, False

    try:
        for season_code in candidates:
            fetched_at = _now_iso(now)
            try:
                games = source.fetch_games(season_code)
            except Exception as e:
                log.warning("%s: games list fetch failed: %s", season_code, e)
                stats.errors.append(f"{season_code} games: {e}")
                continue
            for key, raw in games.raw_pages:
                db.store_raw(conn, source.name, "games", key, raw, fetched_at)
            db.upsert_games(conn, source.name, games.rows, fetched_at)
            db.upsert_clubs(conn, source.name, season_code, games.clubs)
            conn.commit()

            if newest_played_only and not any(r["played"] for r in games.rows):
                log.info("%s: no played games yet, trying previous season", season_code)
                continue

            stats.seasons_processed.append(season_code)
            _refresh_people_if_stale(conn, source, season_code, now, stats)
            _process_game_details(conn, source, season_code, limit, now, stats)

            if newest_played_only:
                break
            if limit is not None and stats.games_processed >= limit:
                break
    except AbortRun as e:
        log.error("run aborted: %s", e)
        stats.errors.append(f"aborted: {e}")

    stats.requests_made = source.requests_made
    finished_at = _now_iso(now)
    if not stats.errors:
        db.meta_set(conn, "last_successful_ingest_at", finished_at)
    db.finish_run(conn, run_id, finished_at, stats.requests_made,
                  stats.games_processed, len(stats.errors))
    return stats


def _refresh_people_if_stale(conn, source: Source, season_code: str,
                             now: datetime | None, stats: RunStats) -> None:
    meta_key = f"people_synced_at:{source.name}:{season_code}"
    synced_at = db.meta_get(conn, meta_key)
    now_dt = now or datetime.now(UTC)
    if synced_at and now_dt - datetime.fromisoformat(synced_at) < PEOPLE_REFRESH:
        return
    fetched_at = _now_iso(now)
    try:
        people = source.fetch_people(season_code)
    except Exception as e:
        log.warning("%s: people fetch failed: %s", season_code, e)
        stats.errors.append(f"{season_code} people: {e}")
        return
    for key, raw in people.raw_pages:
        db.store_raw(conn, source.name, "people", key, raw, fetched_at)
    db.upsert_people(conn, source.name, season_code, people.rows)
    db.meta_set(conn, meta_key, fetched_at)
    conn.commit()
    log.info("%s: people registry refreshed (%d entries)", season_code, len(people.rows))


def _process_game_details(conn, source: Source, season_code: str,
                          limit: int | None, now: datetime | None,
                          stats: RunStats) -> None:
    pending = conn.execute(
        """SELECT game_code, home_club_code, away_club_code FROM games
           WHERE source=? AND season_code=? AND played=1 AND is_final=0
           ORDER BY game_code""",
        (source.name, season_code),
    ).fetchall()
    total = len(pending)
    log.info("%s: %d played game(s) pending details", season_code, total)

    consecutive_errors = 0
    for i, g in enumerate(pending, 1):
        if limit is not None and stats.games_processed >= limit:
            log.info("game limit (%d) reached", limit)
            return
        game_code = g["game_code"]
        try:
            box = source.fetch_boxscore(season_code, game_code,
                                        g["home_club_code"], g["away_club_code"])
            pbp = source.fetch_pbp(season_code, game_code)
        except Exception as e:
            log.warning("%s game %s: %s", season_code, game_code, e)
            stats.errors.append(f"{season_code} g{game_code}: {e}")
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                raise AbortRun(f"{consecutive_errors} consecutive game failures") from e
            continue
        consecutive_errors = 0

        fetched_at = _now_iso(now)
        game_key = f"{season_code}:{game_code}"
        if box.raw is not None:
            db.store_raw(conn, source.name, "boxscore", game_key, box.raw, fetched_at)
        if box.found:
            db.replace_boxscore_lines(conn, source.name, season_code, game_code, box.rows)
        if pbp.raw is not None:
            db.store_raw(conn, source.name, "pbp", game_key, pbp.raw, fetched_at)
        if pbp.found:
            db.replace_pbp_events(conn, source.name, season_code, game_code, pbp.rows)

        box_status = "ok" if box.found else "missing"
        pbp_status = "ok" if pbp.found else "missing"
        is_final = 0 if pbp.live else 1
        db.set_game_ingest_state(conn, source.name, season_code, game_code,
                                 box_status, pbp_status, is_final, fetched_at)
        conn.commit()

        stats.games_processed += 1
        stats.games_finalized += is_final
        stats.boxscores_missing += box_status == "missing"
        stats.pbp_missing += pbp_status == "missing"
        log.info("%s game %s: boxscore=%s pbp=%s%s (%d/%d)",
                 season_code, game_code, box_status, pbp_status,
                 " LIVE" if pbp.live else "", i, total)
