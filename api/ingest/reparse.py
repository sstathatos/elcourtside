"""Re-parse stored raw payloads into the parsed tables — zero network."""

from __future__ import annotations

import json
import logging
import zlib

from ingest import db
from ingest.sources import euroleague as el

log = logging.getLogger("ingest")


def _load(payload: bytes) -> object | None:
    try:
        return json.loads(zlib.decompress(payload).decode("utf-8-sig"))
    except (ValueError, zlib.error):
        return None


def _items(doc: object) -> list[dict]:
    """Both list endpoints answer either bare or wrapped in {'data': [...]}."""
    if isinstance(doc, dict):
        doc = doc.get("data") or []
    return [i for i in doc if isinstance(i, dict)] if isinstance(doc, list) else []


def reparse_registries(conn, source: str, season_codes: list[str]) -> dict[str, int]:
    """Re-derive the club and people registries — including image URLs, which older ingests parsed past — from stored payloads."""
    counts = {"clubs": 0, "people": 0}
    for season in season_codes:
        rows = conn.execute(
            """SELECT kind, key, payload FROM raw_payloads
               WHERE source=? AND kind IN ('games', 'people') AND key LIKE ?""",
            (source, f"{season}:%"),
        ).fetchall()
        with conn:
            for r in rows:
                doc = _load(r["payload"])
                if doc is None:
                    continue
                items = _items(doc)
                if r["kind"] == "games":
                    clubs = el.parse_clubs(items)
                    if clubs:
                        db.upsert_clubs(conn, source, season, clubs)
                        counts["clubs"] += len(clubs)
                else:
                    people = el.parse_people(items)
                    if people:
                        db.upsert_people(conn, source, season, people)
                        counts["people"] += len(people)
    return counts


def reparse_details(conn, source: str, season_codes: list[str]) -> dict[str, int]:
    counts = {"boxscore": 0, "pbp": 0, "skipped": 0}
    for season in season_codes:
        clubs = {
            r["game_code"]: (r["home_club_code"], r["away_club_code"])
            for r in conn.execute(
                "SELECT game_code, home_club_code, away_club_code FROM games"
                " WHERE source=? AND season_code=?", (source, season))
        }
        rows = conn.execute(
            """SELECT kind, key, payload FROM raw_payloads
               WHERE source=? AND kind IN ('boxscore', 'pbp') AND key LIKE ?""",
            (source, f"{season}:%"),
        ).fetchall()
        with conn:
            for r in rows:
                game_code = int(r["key"].split(":", 1)[1])
                try:
                    doc = json.loads(zlib.decompress(r["payload"]).decode("utf-8-sig"))
                except (ValueError, zlib.error):
                    counts["skipped"] += 1
                    continue
                if r["kind"] == "boxscore":
                    home, away = clubs.get(game_code, (None, None))
                    lines = el.parse_boxscore(doc, home, away)
                    if lines:
                        db.replace_boxscore_lines(conn, source, season, game_code, lines)
                        counts["boxscore"] += 1
                else:
                    events, _live = el.parse_pbp(doc)
                    if events:
                        db.replace_pbp_events(conn, source, season, game_code, events)
                        counts["pbp"] += 1
        log.info("%s: reparsed from raw", season)
    return counts


def resolve_db_seasons(conn, source: str, selector: str) -> list[str]:
    rows = conn.execute(
        """SELECT g.season_code FROM games g
           JOIN seasons s ON s.source=g.source AND s.code=g.season_code
           WHERE g.source=? GROUP BY g.season_code ORDER BY s.year""",
        (source,),
    ).fetchall()
    available = [r["season_code"] for r in rows]
    if selector == "all":
        return available
    if selector == "latest":
        return available[-1:]
    requested = [c.strip() for c in selector.split(",") if c.strip()]
    unknown = set(requested) - set(available)
    if unknown:
        raise SystemExit(f"season(s) not in DB: {', '.join(sorted(unknown))}")
    return requested
