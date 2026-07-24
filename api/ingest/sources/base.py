"""Common source interface.

A source turns remote APIs into (a) raw payload pages to archive and
(b) parsed rows shaped exactly like the DB tables in ingest/db.py.
The pipeline never sees source-specific JSON.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class FetchedList:
    """Result of a list endpoint (seasons, games, people); may span pages."""
    raw_pages: list[tuple[str, bytes]] = field(default_factory=list)  # (raw key, body)
    rows: list[dict] = field(default_factory=list)


@dataclass
class FetchedGameDetail:
    """Result of a per-game endpoint (boxscore, play-by-play).

    found=False means the API answered but has no data for this game
    (e.g. play-by-play before 2007) — recorded as 'missing', not an error.
    """
    raw: bytes | None = None
    rows: list[dict] = field(default_factory=list)
    found: bool = False
    live: bool = False  # play-by-play only: game still in progress


class Source(abc.ABC):
    name: str

    @abc.abstractmethod
    def fetch_seasons(self) -> FetchedList: ...

    @abc.abstractmethod
    def fetch_games(self, season_code: str) -> FetchedList: ...

    @abc.abstractmethod
    def fetch_people(self, season_code: str) -> FetchedList: ...

    @abc.abstractmethod
    def fetch_boxscore(self, season_code: str, game_code: int,
                       home_club_code: str | None, away_club_code: str | None) -> FetchedGameDetail: ...

    @abc.abstractmethod
    def fetch_pbp(self, season_code: str, game_code: int) -> FetchedGameDetail: ...

    @property
    def requests_made(self) -> int:
        return 0
