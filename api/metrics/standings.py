"""Regular-season standings with Euroleague-style tiebreaks.

Ranking: wins. Ties are broken by a mini-league of the games between the
tied clubs — (1) head-to-head wins, (2) head-to-head point diff — then
(3) overall point diff, (4) overall points scored. This covers the primary
official criteria; edge cases deeper in the official rulebook (e.g.
re-splitting after a partial tie-break) are intentionally not modeled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import groupby


@dataclass
class TeamRecord:
    club_code: str
    club_name: str = ""
    wins: int = 0
    losses: int = 0
    points_for: int = 0
    points_against: int = 0
    rank: int = 0
    _h2h: dict = field(default_factory=dict, repr=False)  # set per tie group

    @property
    def games(self) -> int:
        return self.wins + self.losses

    @property
    def point_diff(self) -> int:
        return self.points_for - self.points_against


def compute_standings(games: list[dict]) -> list[TeamRecord]:
    """games: played regular-season rows with home/away club codes+scores."""
    records: dict[str, TeamRecord] = {}

    def rec(code: str, name: str) -> TeamRecord:
        if code not in records:
            records[code] = TeamRecord(club_code=code, club_name=name)
        return records[code]

    for g in games:
        home = rec(g["home_club_code"], g["home_club_name"] or "")
        away = rec(g["away_club_code"], g["away_club_name"] or "")
        hs, as_ = g["home_score"] or 0, g["away_score"] or 0
        home.points_for += hs
        home.points_against += as_
        away.points_for += as_
        away.points_against += hs
        if hs > as_:
            home.wins += 1
            away.losses += 1
        else:
            away.wins += 1
            home.losses += 1

    ordered = sorted(records.values(), key=lambda r: -r.wins)
    result: list[TeamRecord] = []
    for _, group in groupby(ordered, key=lambda r: r.wins):
        tied = list(group)
        if len(tied) > 1:
            tied = _break_ties(tied, games)
        result.extend(tied)
    for i, r in enumerate(result, 1):
        r.rank = i
    return result


def _break_ties(tied: list[TeamRecord], games: list[dict]) -> list[TeamRecord]:
    codes = {r.club_code for r in tied}
    h2h = {c: {"wins": 0, "diff": 0} for c in codes}
    for g in games:
        h, a = g["home_club_code"], g["away_club_code"]
        if h not in codes or a not in codes:
            continue
        hs, as_ = g["home_score"] or 0, g["away_score"] or 0
        h2h[h]["diff"] += hs - as_
        h2h[a]["diff"] += as_ - hs
        h2h[h if hs > as_ else a]["wins"] += 1
    return sorted(tied, key=lambda r: (
        -h2h[r.club_code]["wins"],
        -h2h[r.club_code]["diff"],
        -r.point_diff,
        -r.points_for,
    ))
