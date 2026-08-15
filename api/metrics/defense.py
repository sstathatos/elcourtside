"""On-court defensive impact: what the opposition did while a player was out there."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from metrics.lineups import GameLineups
from metrics.timeline import Timeline

FG_MADE = {"2FGM", "3FGM"}
FG_MISSED = {"2FGA", "3FGA"}


@dataclass
class OnCourtDefense:
    """Opponent totals accumulated while each player was on court."""

    opp_fgm: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    opp_fga: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    opp_points: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def players(self) -> set[str]:
        return set(self.opp_fgm) | set(self.opp_fga) | set(self.opp_points)


def compute_on_court_defense(timeline: Timeline, lineups: GameLineups) -> OnCourtDefense:
    """Attribute every opponent shot and point to the five players facing it."""
    out = OnCourtDefense()

    for e in timeline.events:
        on_home, on_away = lineups.states[e.index]

        if e.delta_home:
            for p in on_away:
                out.opp_points[p] += e.delta_home
        if e.delta_away:
            for p in on_home:
                out.opp_points[p] += e.delta_away

        made = e.play_type in FG_MADE
        missed = e.play_type in FG_MISSED
        if not (made or missed):
            continue
        if e.team_code == timeline.home_club:
            defenders = on_away
        elif e.team_code == timeline.away_club:
            defenders = on_home
        else:
            continue
        for p in defenders:
            out.opp_fga[p] += 1
            if made:
                out.opp_fgm[p] += 1

    return out
