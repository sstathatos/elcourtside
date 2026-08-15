"""Clutch stats: last 5:00 of the 4th quarter or any overtime, with the score margin ≤ 5 — evaluated moment by moment, not per game."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from metrics.lineups import GameLineups
from metrics.timeline import REGULATION, Timeline

CLUTCH_WINDOW_START = REGULATION - 300.0  # 35:00 — last 5 min of Q4; all OT
CLUTCH_MARGIN = 5


@dataclass
class ClutchStats:
    game_seconds: float = 0.0                 # clutch time existing in this game
    player_seconds: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    player_points: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    player_pm: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    home_pts_for: int = 0
    away_pts_for: int = 0


def _clutch_overlap(t1: float, t2: float, duration: float) -> float:
    lo = max(t1, CLUTCH_WINDOW_START)
    hi = min(t2, duration)
    return max(0.0, hi - lo)


def compute_clutch(timeline: Timeline, lineups: GameLineups) -> ClutchStats:
    stats = ClutchStats()
    events = timeline.events
    if not events:
        return stats

    for i, e in enumerate(events):
        t1 = e.abs_s
        t2 = events[i + 1].abs_s if i + 1 < len(events) else timeline.duration
        if t2 <= t1:
            continue
        margin = abs(e.home_after - e.away_after)
        if margin > CLUTCH_MARGIN:
            continue
        dt = _clutch_overlap(t1, t2, timeline.duration)
        if dt <= 0:
            continue
        stats.game_seconds += dt
        on_home, on_away = lineups.states[e.index]
        for p in on_home | on_away:
            stats.player_seconds[p] += dt

    for e in events:
        dh, da = e.delta_home, e.delta_away
        if dh == 0 and da == 0:
            continue
        if e.abs_s < CLUTCH_WINDOW_START:
            continue
        if abs(e.home_before - e.away_before) > CLUTCH_MARGIN:
            continue
        stats.home_pts_for += dh
        stats.away_pts_for += da
        if e.player_code:
            stats.player_points[e.player_code] += dh + da  # only one side is non-zero
        on_home, on_away = lineups.states[e.index]
        for p in on_home:
            stats.player_pm[p] += dh - da
        for p in on_away:
            stats.player_pm[p] += da - dh
    return stats
