"""Pydantic response models — these are what turn /docs into a usable contract.

Deliberately shallow: they mirror the columns metrics writes, so a change to a
metric surfaces here as a field, not as an untyped blob. Composite payloads
(game/team/player detail) allow extra keys so adding a column to a rollup does
not require touching this file to keep it visible.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class PlayerSort(str, Enum):
    """Whitelist for ORDER BY on the player leaderboard.

    Anything not in this enum is rejected by FastAPI with a 422 before it can
    reach SQL — a column name can't be a bound parameter, so this is what
    keeps `?sort=` from becoming an injection point.
    """

    pir_avg = "pir_avg"
    pir_total = "pir_total"
    pir_per36 = "pir_per36"
    pm_total = "pm_total"
    pm_per36 = "pm_per36"
    points = "points"
    clutch_pm = "clutch_pm"
    clutch_points = "clutch_points"
    fouls_drawn_per100 = "fouls_drawn_per100"


class Phase(str, Enum):
    """Competition stage. Standings mean the regular season; the knockout
    stages are results rather than a table."""

    RS = "RS"
    PI = "PI"
    PO = "PO"
    FF = "FF"


class TeamSort(str, Enum):
    possessions_avg = "possessions_avg"
    fouls_drawn_per100 = "fouls_drawn_per100"
    max_run = "max_run"
    max_blown_lead = "max_blown_lead"
    clutch_pts_for = "clutch_pts_for"


class Season(BaseModel):
    season_code: str
    season_name: str | None = None
    year: int | None = None
    # The club that won the title. Not the top of the standings — those rank
    # the regular season, and the Final Four decides the championship.
    winner_club_code: str | None = None
    games: int
    games_with_pbp: int
    computed_at: str | None = None

    @property
    def has_pbp(self) -> bool:
        return self.games_with_pbp > 0


class StandingsRow(BaseModel):
    club_code: str
    club_name: str | None = None
    games: int | None = None
    wins: int | None = None
    losses: int | None = None
    points_for: int | None = None
    points_against: int | None = None
    point_diff: int | None = None
    rank: int | None = None


class GameSummary(BaseModel):
    game_code: int
    round: int | None = None
    round_name: str | None = None
    phase_type_code: str | None = None
    utc_date: str | None = None
    played: int | None = None
    home_club_code: str | None = None
    home_club_name: str | None = None
    home_score: int | None = None
    away_club_code: str | None = None
    away_club_name: str | None = None
    away_score: int | None = None
    winner_club_code: str | None = None
    pbp_status: str | None = None


class GameDetail(GameSummary):
    model_config = ConfigDict(extra="allow")

    boxscore: list[dict]
    player_metrics: list[dict]
    team_metrics: list[dict]


class TimelinePoint(BaseModel):
    t: float
    quarter: int
    ot: int
    home: int
    away: int
    play_type: str | None = None
    club_code: str | None = None
    player_code: str | None = None


class GameTimeline(BaseModel):
    game_code: int
    has_pbp: bool
    home_club_code: str | None = None
    away_club_code: str | None = None
    home_final: int | None = None
    away_final: int | None = None
    duration: float | None = None
    n_ot: int | None = None
    points: list[TimelinePoint]


class TeamSeason(BaseModel):
    model_config = ConfigDict(extra="allow")

    club_code: str
    club_name: str | None = None
    games: int | None = None
    possessions_avg: float | None = None
    fouls_drawn_per100: float | None = None
    max_run: int | None = None
    max_run_game: int | None = None
    max_blown_lead: int | None = None
    max_blown_lead_game: int | None = None
    clutch_pts_for: int | None = None
    clutch_pts_against: int | None = None
    clutch_seconds: float | None = None
    wins: int | None = None
    losses: int | None = None
    point_diff: int | None = None
    rank: int | None = None


class RadarAxis(BaseModel):
    key: str
    label: str
    value: float
    percentile: float  # rank against the league, 0-100 — the radar's only scale
    # True where a smaller raw value is better (turnovers, opponent shooting).
    # The percentile is already flipped, so the radar still reads
    # "further out is better"; this flags it for the label and the table.
    lower_is_better: bool = False


class TeamDetail(TeamSeason):
    games: list[dict]  # game log; shadows the season count on purpose
    roster: list[dict] = []  # registered squad, including players yet to appear
    radar: list[RadarAxis] = []


class PlayerSeason(BaseModel):
    model_config = ConfigDict(extra="allow")

    player_code: str
    player_name: str | None = None
    clubs: str | None = None
    games_played: int | None = None
    seconds: float | None = None
    points: int | None = None
    reb_total: int | None = None
    assists: int | None = None
    steals: int | None = None
    blocks_favour: int | None = None
    turnovers: int | None = None
    fouls_drawn: int | None = None
    pir_total: int | None = None
    pir_avg: float | None = None
    pir_per36: float | None = None
    pm_total: int | None = None
    pm_per36: float | None = None
    clutch_seconds: float | None = None
    clutch_points: int | None = None
    clutch_pm: int | None = None
    fouls_drawn_per100: float | None = None
    headshot_url: str | None = None


class PlayerDetail(PlayerSeason):
    games: list[dict]
    # Null for the ~3% of players the registry has no photo for, and for
    # everyone who is not a player (coaches and staff carry no images at all).
    headshot_url: str | None = None
    action_url: str | None = None
    # Empty for players below the games threshold, where a per-36 rate is noise
    radar: list[RadarAxis] = []


class Club(BaseModel):
    club_code: str
    club_name: str | None = None
    crest_url: str | None = None


class RunRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    game_code: int
    club_code: str
    opponent_code: str | None = None
    max_run: int | None = None
    max_run_detail: str | None = None
    points: int | None = None
    utc_date: str | None = None
    round: int | None = None


class BlownLeadRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    game_code: int
    club_code: str
    opponent_code: str | None = None
    max_lead: int | None = None
    points: int | None = None
    opponent_points: int | None = None
    utc_date: str | None = None
    round: int | None = None


class ClutchIndex(BaseModel):
    players: list[dict]
    teams: list[dict]


class FoulsDrawnIndex(BaseModel):
    players: list[dict]
    teams: list[dict]


class Health(BaseModel):
    status: str
    database: str
    seasons: int
    cache: dict
