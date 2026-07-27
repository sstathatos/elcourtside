"""Reconstruct who was on court from starters + IN/OUT events.

The trickiest parser (see doc/plan.md). Defensive against real-world PBP
messiness, all counted as anomalies rather than errors:
- IN/OUT pairs at the same clock arrive in either order → same-club subs at
  identical timestamps are batched, OUTs applied before INs;
- OUT with no prior IN (missing IN event) → assume the player entered at
  the start of the current period;
- double IN, or a club transiently above 5 on court → recorded, tolerated.

Ground truth check: computed per-player seconds are reconciled against the
boxscore's timePlayed by the --validate command.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from metrics.timeline import SUB_TYPES, Timeline, _period_bounds


@dataclass
class GameLineups:
    # per timeline-event index: (home on-court, away on-court) in effect at
    # that event (subs earlier in PBP order already applied)
    states: list[tuple[frozenset, frozenset]]
    intervals: dict[str, list[tuple[float, float]]]
    seconds: dict[str, float]
    anomalies: list[str] = field(default_factory=list)


def _batched_order(events) -> list[int]:
    """Event indices with same-time sub batches reordered OUT-first.

    A batch is a contiguous run of IN/OUT events sharing one timestamp
    (either club) — the table crew logs swap pairs in arbitrary order."""
    order: list[int] = []
    i = 0
    while i < len(events):
        e = events[i]
        if e.play_type not in SUB_TYPES or not e.team_code:
            order.append(i)
            i += 1
            continue
        j = i
        while (j < len(events) and events[j].play_type in SUB_TYPES
               and events[j].abs_s == e.abs_s):
            j += 1
        batch = sorted(range(i, j), key=lambda k: 0 if events[k].play_type == "OUT" else 1)
        order.extend(batch)
        i = j
    return order


def track_lineups(timeline: Timeline, home_starters: set[str],
                  away_starters: set[str]) -> GameLineups:
    events = timeline.events
    anomalies: list[str] = []
    for club, starters in ((timeline.home_club, home_starters),
                           (timeline.away_club, away_starters)):
        if len(starters) != 5:
            anomalies.append(f"{club}: {len(starters)} starters flagged")

    entry: dict[str, dict[str, float]] = {
        timeline.home_club: {p: 0.0 for p in home_starters},
        timeline.away_club: {p: 0.0 for p in away_starters},
    }
    intervals: dict[str, list[tuple[float, float]]] = defaultdict(list)
    states: list[tuple[frozenset, frozenset] | None] = [None] * len(events)

    for k in _batched_order(events):
        e = events[k]
        if e.play_type in SUB_TYPES and e.team_code in entry and e.player_code:
            on = entry[e.team_code]
            if e.play_type == "OUT":
                if e.player_code in on:
                    start = on.pop(e.player_code)
                    intervals[e.player_code].append((start, e.abs_s))
                else:
                    period_start, _ = _period_bounds(e.quarter, e.ot)
                    start = min(period_start, e.abs_s)
                    intervals[e.player_code].append((start, e.abs_s))
                    anomalies.append(
                        f"{e.team_code} {e.player_code}: OUT without IN @{e.abs_s:.0f}s,"
                        f" assumed on since {start:.0f}s")
            else:  # IN
                if e.player_code in on:
                    anomalies.append(f"{e.team_code} {e.player_code}: double IN @{e.abs_s:.0f}s")
                else:
                    on[e.player_code] = e.abs_s
                    if len(on) > 5:
                        anomalies.append(
                            f"{e.team_code}: {len(on)} on court after IN "
                            f"{e.player_code} @{e.abs_s:.0f}s")
        states[k] = (frozenset(entry[timeline.home_club]),
                     frozenset(entry[timeline.away_club]))

    # _batched_order permutes only within same-time sub batches, so filling
    # any stragglers in index order keeps states consistent
    last = (frozenset(home_starters), frozenset(away_starters))
    final_states: list[tuple[frozenset, frozenset]] = []
    for s in states:
        last = s if s is not None else last
        final_states.append(last)

    for on in entry.values():
        for player, start in on.items():
            intervals[player].append((start, timeline.duration))

    seconds = {p: sum(e - s for s, e in iv) for p, iv in intervals.items()}
    return GameLineups(states=final_states, intervals=dict(intervals),
                       seconds=seconds, anomalies=anomalies)
