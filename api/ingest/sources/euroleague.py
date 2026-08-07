"""Euroleague source.

Endpoints (all unauthenticated, verified July 2026):
- https://api-live.euroleague.net/v2/... — seasons, games, boxscores, people.
  List endpoints return {"data": [...], "total": N}, 500 items per page,
  paginated with ?offset=.
- https://live.euroleague.net/api/PlayByPlay?gamecode=&seasoncode= — PBP.
  Quarter arrays (FirstQuarter..ForthQuarter [sic], ExtraTime) + Live flag.
  Empty/absent for seasons before E2007.

Quirks handled here so the rest of the codebase never sees them:
- PBP CODETEAM / PLAYER_ID are space-padded; PLAYER_ID has a 'P' prefix that
  boxscore/people person codes don't ("P007200" vs "007200").
- The boxscore payload does not identify the clubs — local/road club codes
  must be passed in from the games table.
"""

from __future__ import annotations

import json

from ingest.client import NotFoundError, PoliteClient
from ingest.sources.base import FetchedGameDetail, FetchedList, Source

V2 = "https://api-live.euroleague.net/v2"
PBP_URL = "https://live.euroleague.net/api/PlayByPlay"

PBP_QUARTERS = [
    ("FirstQuarter", 1),
    ("SecondQuarter", 2),
    ("ThirdQuarter", 3),
    ("ForthQuarter", 4),   # sic — API's spelling
    ("ExtraTime", 5),
]


def normalize_person_code(value: str | None) -> str:
    """Person codes as used by boxscore/people: just trim padding."""
    return (value or "").strip()


def normalize_pbp_player_id(value: str | None) -> str:
    """PBP PLAYER_IDs prefix *every* person code with 'P' — numeric
    ('P007200' vs '007200') and legacy alphanumeric ('PTGB' vs 'TGB', Llull)
    alike — so one leading 'P' is always stripped. Bench pseudo-codes like
    'CO_A' (coach) don't start with 'P' and pass through untouched."""
    s = (value or "").strip()
    if len(s) > 1 and s.startswith("P"):
        return s[1:]
    return s


def _i(v) -> int | None:
    return None if v is None else int(round(float(v)))


# -- pure parsers (fixture-tested) --------------------------------------------

def parse_seasons(items: list[dict]) -> list[dict]:
    return [
        {
            "code": s.get("code"),
            "name": s.get("name"),
            "alias": s.get("alias"),
            "year": s.get("year"),
            "start_date": s.get("startDate"),
            "end_date": s.get("endDate"),
            "winner_club_code": (s.get("winner") or {}).get("code"),
        }
        for s in items
    ]


def parse_games(items: list[dict], season_code: str) -> list[dict]:
    rows = []
    for g in items:
        local, road = g.get("local") or {}, g.get("road") or {}
        rows.append({
            "season_code": season_code,
            "game_code": g.get("gameCode"),
            "identifier": g.get("identifier"),
            "utc_date": g.get("utcDate"),
            "local_date": g.get("localDate") or g.get("date"),
            "round": g.get("round"),
            "round_name": g.get("roundName"),
            "phase_type_code": (g.get("phaseType") or {}).get("code"),
            "phase_type_name": (g.get("phaseType") or {}).get("name"),
            "group_name": ((g.get("group") or {}).get("rawName") or "").strip(),
            "played": 1 if g.get("played") else 0,
            "game_status": g.get("gameStatus"),
            "home_club_code": (local.get("club") or {}).get("code"),
            "home_club_name": (local.get("club") or {}).get("name"),
            "home_score": local.get("score"),
            "away_club_code": (road.get("club") or {}).get("code"),
            "away_club_name": (road.get("club") or {}).get("name"),
            "away_score": road.get("score"),
            "home_partials": json.dumps(local["partials"]) if local.get("partials") else None,
            "away_partials": json.dumps(road["partials"]) if road.get("partials") else None,
            "winner_club_code": (g.get("winner") or {}).get("code"),
            "audience": g.get("audience"),
        })
    return rows


def _stat_fields(st: dict) -> dict:
    return {
        "seconds_played": st.get("timePlayed"),
        "points": _i(st.get("points")),
        "fg2m": _i(st.get("fieldGoalsMade2")),
        "fg2a": _i(st.get("fieldGoalsAttempted2")),
        "fg3m": _i(st.get("fieldGoalsMade3")),
        "fg3a": _i(st.get("fieldGoalsAttempted3")),
        "ftm": _i(st.get("freeThrowsMade")),
        "fta": _i(st.get("freeThrowsAttempted")),
        "reb_off": _i(st.get("offensiveRebounds")),
        "reb_def": _i(st.get("defensiveRebounds")),
        "reb_total": _i(st.get("totalRebounds")),
        "assists": _i(st.get("assistances")),
        "steals": _i(st.get("steals")),
        "turnovers": _i(st.get("turnovers")),
        "blocks_favour": _i(st.get("blocksFavour")),
        "blocks_against": _i(st.get("blocksAgainst")),
        "fouls_committed": _i(st.get("foulsCommited")),   # sic — API's spelling
        "fouls_received": _i(st.get("foulsReceived")),
        "plus_minus": _i(st.get("plusMinus")),
        "valuation": _i(st.get("valuation")),
    }


def parse_boxscore(doc: dict, home_club_code: str | None,
                   away_club_code: str | None) -> list[dict]:
    rows: list[dict] = []
    sides = [("local", 1, home_club_code), ("road", 0, away_club_code)]
    for side_key, is_home, club_code in sides:
        side = (doc or {}).get(side_key) or {}
        for p in side.get("players") or []:
            player = p.get("player") or {}
            person = player.get("person") or {}
            st = p.get("stats") or {}
            rows.append({
                "is_home": is_home,
                "entry_type": "player",
                "player_code": normalize_person_code(person.get("code")),
                "club_code": club_code,
                "player_name": person.get("name"),
                "dorsal": str(st.get("dorsal") if st.get("dorsal") is not None
                              else player.get("dorsal") or ""),
                "start_five": 1 if st.get("startFive") else 0,
                **_stat_fields(st),
            })
        for entry_type in ("team", "total"):
            st = side.get(entry_type)
            if st:
                rows.append({
                    "is_home": is_home,
                    "entry_type": entry_type,
                    "player_code": "",
                    "club_code": club_code,
                    "player_name": None,
                    "dorsal": None,
                    "start_five": None,
                    **_stat_fields(st),
                })
    return rows


def parse_pbp(doc) -> tuple[list[dict], bool]:
    """Return (event rows, live). Empty rows == no PBP for this game."""
    if not isinstance(doc, dict):
        return [], False
    live = bool(doc.get("Live"))
    rows: list[dict] = []
    for key, quarter in PBP_QUARTERS:
        for idx, ev in enumerate(doc.get(key) or []):
            play_number = ev.get("NUMBEROFPLAY")
            if play_number is None:
                play_number = -(idx + 1)  # keep PK non-null; order preserved
            rows.append({
                "quarter": quarter,
                "play_number": play_number,
                "play_type": (ev.get("PLAYTYPE") or "").strip(),
                "team_code": (ev.get("CODETEAM") or "").strip(),
                "player_code": normalize_pbp_player_id(ev.get("PLAYER_ID")),
                "player_name": ev.get("PLAYER"),
                "dorsal": ev.get("DORSAL"),
                "minute": ev.get("MINUTE"),
                "marker_time": ev.get("MARKERTIME"),
                "points_a": ev.get("POINTS_A"),
                "points_b": ev.get("POINTS_B"),
                "play_info": ev.get("PLAYINFO"),
                "comment": ev.get("COMMENT"),
            })
    return rows, live


def parse_people(items: list[dict]) -> list[dict]:
    rows = []
    for p in items:
        person = p.get("person") or {}
        # `images` appears on both the entry and the nested person; the entry
        # wins where both are set. Players carry headshot/action (identical
        # URLs in practice); coaches and staff carry an empty object.
        images = {**(person.get("images") or {}), **(p.get("images") or {})}
        rows.append({
            "person_code": normalize_person_code(person.get("code")),
            "club_code": (p.get("club") or {}).get("code") or "",
            "type_code": p.get("type") or "",
            "name": person.get("name"),
            "type_name": p.get("typeName"),
            "active": 1 if p.get("active") else 0,
            "dorsal": p.get("dorsal"),
            "position": p.get("position"),
            "position_name": p.get("positionName"),
            "height": person.get("height"),
            "birth_date": person.get("birthDate"),
            "country_code": (person.get("country") or {}).get("code"),
            "start_date": p.get("startDate"),
            "end_date": p.get("endDate"),
            "headshot_url": images.get("headshot") or None,
            "action_url": images.get("action") or None,
        })
    return rows


def parse_clubs(items: list[dict]) -> list[dict]:
    """Club registry from a schedule payload — every club appears on one side
    or the other. Later rows win, so a club named differently mid-season keeps
    its most recent name."""
    clubs: dict[str, dict] = {}
    for g in items:
        for side in ("local", "road"):
            club = (g.get(side) or {}).get("club") or {}
            code = club.get("code")
            if not code:
                continue
            clubs[code] = {
                "club_code": code,
                "club_name": club.get("name"),
                "crest_url": (club.get("images") or {}).get("crest") or None,
            }
    return list(clubs.values())


# -- source -------------------------------------------------------------------

class EuroleagueSource(Source):
    name = "euroleague"

    def __init__(self, client: PoliteClient, competition: str = "E"):
        self.client = client
        self.competition = competition

    @property
    def requests_made(self) -> int:
        return self.client.requests_made

    def _paged(self, url: str) -> tuple[list[tuple[str, bytes]], list[dict]]:
        """Fetch a {data, total} list endpoint across all ?offset= pages."""
        raw_pages: list[tuple[str, bytes]] = []
        items: list[dict] = []
        while True:
            params = {"offset": len(items)} if items else None
            raw, doc = self.client.get_json(url, params=params)
            if not isinstance(doc, dict) or "data" not in doc:
                raise ValueError(f"unexpected payload from {url}")
            raw_pages.append((str(len(items)), raw))
            page = doc.get("data") or []
            items.extend(page)
            total = doc.get("total")
            if not page or total is None or len(items) >= total:
                return raw_pages, items

    def fetch_seasons(self) -> FetchedList:
        url = f"{V2}/competitions/{self.competition}/seasons"
        raw_pages, items = self._paged(url)
        return FetchedList(raw_pages=raw_pages, rows=parse_seasons(items))

    def fetch_games(self, season_code: str) -> FetchedList:
        url = f"{V2}/competitions/{self.competition}/seasons/{season_code}/games"
        raw_pages, items = self._paged(url)
        return FetchedList(
            raw_pages=[(f"{season_code}:{off}", raw) for off, raw in raw_pages],
            rows=parse_games(items, season_code),
            clubs=parse_clubs(items),
        )

    def fetch_people(self, season_code: str) -> FetchedList:
        url = f"{V2}/competitions/{self.competition}/seasons/{season_code}/people"
        raw_pages, items = self._paged(url)
        return FetchedList(
            raw_pages=[(f"{season_code}:{off}", raw) for off, raw in raw_pages],
            rows=parse_people(items),
        )

    def fetch_boxscore(self, season_code: str, game_code: int,
                       home_club_code: str | None, away_club_code: str | None) -> FetchedGameDetail:
        url = f"{V2}/competitions/{self.competition}/seasons/{season_code}/games/{game_code}/stats"
        try:
            raw, doc = self.client.get_json(url)
        except NotFoundError:
            return FetchedGameDetail(found=False)
        rows = parse_boxscore(doc, home_club_code, away_club_code) if isinstance(doc, dict) else []
        return FetchedGameDetail(raw=raw, rows=rows, found=bool(rows))

    def fetch_pbp(self, season_code: str, game_code: int) -> FetchedGameDetail:
        try:
            raw, doc = self.client.get_json(
                PBP_URL, params={"gamecode": game_code, "seasoncode": season_code}
            )
        except NotFoundError:
            return FetchedGameDetail(found=False)
        rows, live = parse_pbp(doc)
        return FetchedGameDetail(raw=raw, rows=rows, found=bool(rows), live=live)
