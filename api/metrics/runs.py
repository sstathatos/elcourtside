"""Scoring runs: longest streak of unanswered points per club per game, read off the score timeline (deltas, not event team codes — robust to mislabeled events)."""

from __future__ import annotations

from dataclasses import dataclass

from metrics.timeline import Timeline


@dataclass
class Run:
    club_code: str
    points: int
    start_s: float
    end_s: float


def max_runs(timeline: Timeline) -> dict[str, Run]:
    """Best run per club; clubs without a run map to a 0-point Run."""
    best = {
        timeline.home_club: Run(timeline.home_club, 0, 0.0, 0.0),
        timeline.away_club: Run(timeline.away_club, 0, 0.0, 0.0),
    }
    current: Run | None = None
    for e in timeline.events:
        dh, da = e.delta_home, e.delta_away
        if dh == 0 and da == 0:
            continue
        club = timeline.home_club if dh > 0 else timeline.away_club
        pts = dh + da
        if current is not None and current.club_code == club:
            current.points += pts
            current.end_s = e.abs_s
        else:
            current = Run(club, pts, e.abs_s, e.abs_s)
        if current.points > best[club].points:
            best[club] = Run(club, current.points, current.start_s, current.end_s)
    return best
