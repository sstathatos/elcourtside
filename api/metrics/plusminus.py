"""+/- per player: score deltas attributed to whoever is on court.

Uses the lineup state at each scoring event (PBP order — a basket logged
before a sub at the same clock credits the pre-sub lineup, matching how
the table crew records it). Official boxscore plusMinus is the cross-check.
"""

from __future__ import annotations

from collections import defaultdict

from metrics.lineups import GameLineups
from metrics.timeline import Timeline


def compute_plus_minus(timeline: Timeline, lineups: GameLineups) -> dict[str, int]:
    pm: dict[str, int] = defaultdict(int)
    for e in timeline.events:
        dh, da = e.delta_home, e.delta_away
        if dh == 0 and da == 0:
            continue
        on_home, on_away = lineups.states[e.index]
        for p in on_home:
            pm[p] += dh - da
        for p in on_away:
            pm[p] += da - dh
    return dict(pm)
