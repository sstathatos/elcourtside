"""On-court defensive impact: what the opposition did while a player was out there.

Two numbers the boxscore cannot give you, because they are properties of the
*opponent* rather than of the player:

- **Opponent FG%** — how well the other team shot while this player was on.
- **DRTG** — opponent points per 100 possessions while this player was on.

Both use the same lineup reconstruction that produces +/- (`metrics.lineups`),
so they inherit its one limitation: they need play-by-play, and therefore exist
only for 2007-08 onward.

A caveat worth stating plainly, because these numbers are easy to over-read:
this is on-court attribution, not individual defence. Five players share every
possession, so a weak defender on a strong defensive team looks good here.
Treat it as context, not as a rating.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from metrics.lineups import GameLineups
from metrics.timeline import Timeline

# Field-goal events, by whether they went in. Free throws are deliberately
# excluded from FG%, as they are everywhere else in basketball.
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
    """Attribute every opponent shot and point to the five players facing it.

    The mirror of `compute_plus_minus`: where that credits a scoring team's
    own players, this credits the players who were defending it.
    """
    out = OnCourtDefense()

    for e in timeline.events:
        on_home, on_away = lineups.states[e.index]

        # Points allowed. Taken from the score delta rather than the play type,
        # so free throws, and-ones and any scoring event the feed spells
        # differently are all counted without enumerating them.
        if e.delta_home:
            for p in on_away:
                out.opp_points[p] += e.delta_home
        if e.delta_away:
            for p in on_home:
                out.opp_points[p] += e.delta_away

        # Shooting allowed. `team_code` is the *shooting* team, so the
        # defenders are the other five.
        made = e.play_type in FG_MADE
        missed = e.play_type in FG_MISSED
        if not (made or missed):
            continue
        if e.team_code == timeline.home_club:
            defenders = on_away
        elif e.team_code == timeline.away_club:
            defenders = on_home
        else:
            # An event with no attributable team (feed inconsistency) is
            # skipped rather than guessed at.
            continue
        for p in defenders:
            out.opp_fga[p] += 1
            if made:
                out.opp_fgm[p] += 1

    return out
