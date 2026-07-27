"""PBP rows → absolute-time event stream with running home/away score.

Clock model: MARKERTIME counts down within a period; Q1-4 are 600 s,
each OT 300 s. All extra time is stored as quarter=5 — the OT number is
derived from MINUTE (41-45 → OT1, 46-50 → OT2, ...). Absolute time is
seconds since tip-off; clamped monotonic to survive clock glitches.

Score model: points_a/points_b are cumulative and null means "unchanged".
Which side is "A" is not stored — it is inferred by matching scoring events'
team_code against the club that the increment favors (majority vote).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SCORING_TYPES = {"2FGM", "3FGM", "FTM"}
SUB_TYPES = {"IN", "OUT"}
REGULATION = 2400.0
Q_LEN = 600.0
OT_LEN = 300.0


@dataclass
class Event:
    index: int
    abs_s: float
    quarter: int          # 1-4, 5 = extra time block
    ot: int               # 0 in regulation, OT number otherwise
    play_type: str
    team_code: str
    player_code: str
    home_before: int
    away_before: int
    home_after: int
    away_after: int

    @property
    def delta_home(self) -> int:
        return self.home_after - self.home_before

    @property
    def delta_away(self) -> int:
        return self.away_after - self.away_before


@dataclass
class Timeline:
    events: list[Event]
    home_club: str
    away_club: str
    duration: float
    n_ot: int
    home_final: int
    away_final: int
    a_is_home: bool


def _parse_marker(marker: str | None) -> float | None:
    if not marker or ":" not in marker:
        return None
    try:
        mm, ss = marker.split(":")
        return int(mm) * 60 + int(ss)
    except ValueError:
        return None


def _period_bounds(quarter: int, ot: int) -> tuple[float, float]:
    if quarter <= 4:
        start = (quarter - 1) * Q_LEN
        return start, start + Q_LEN
    start = REGULATION + (ot - 1) * OT_LEN
    return start, start + OT_LEN


def build_timeline(rows: list[dict], home_club: str, away_club: str) -> Timeline:
    rows = sorted(rows, key=lambda r: (r["quarter"], r["play_number"]))

    # pass 1: absolute time, OT numbers, cumulative A/B score, side votes
    staged = []
    cur_a = cur_b = 0
    last_abs = 0.0
    last_ot = 0
    a_votes = 0  # positive → A is home
    n_ot = 0
    for r in rows:
        quarter = r["quarter"]
        if quarter <= 4:
            ot = 0
        else:
            minute = r["minute"]
            ot = math.ceil((minute - 40) / 5) if minute and minute > 40 else max(last_ot, 1)
            last_ot = ot
            n_ot = max(n_ot, ot)
        start, end = _period_bounds(quarter, ot)

        remaining = _parse_marker(r["marker_time"])
        play_type = (r["play_type"] or "").strip()
        if remaining is not None:
            abs_s = end - remaining
        elif play_type == "BP":
            abs_s = start
        elif play_type in ("EP", "EG"):
            abs_s = end
        else:
            abs_s = last_abs
        abs_s = max(abs_s, last_abs)  # monotonic clamp
        last_abs = abs_s

        a_before, b_before = cur_a, cur_b
        new_a = r["points_a"] if r["points_a"] is not None else cur_a
        new_b = r["points_b"] if r["points_b"] is not None else cur_b
        cur_a, cur_b = max(new_a, cur_a), max(new_b, cur_b)  # scores never decrease

        team = r["team_code"] or ""
        if play_type in SCORING_TYPES and team:
            if cur_a > a_before:
                a_votes += 1 if team == home_club else -1
            elif cur_b > b_before:
                a_votes += 1 if team == away_club else -1

        staged.append((r, quarter, ot, abs_s, a_before, b_before, cur_a, cur_b))

    a_is_home = a_votes >= 0

    def to_home_away(a: int, b: int) -> tuple[int, int]:
        return (a, b) if a_is_home else (b, a)

    events = []
    for i, (r, quarter, ot, abs_s, a0, b0, a1, b1) in enumerate(staged):
        h0, w0 = to_home_away(a0, b0)
        h1, w1 = to_home_away(a1, b1)
        events.append(Event(
            index=i, abs_s=abs_s, quarter=quarter, ot=ot,
            play_type=(r["play_type"] or "").strip(),
            team_code=r["team_code"] or "",
            player_code=r["player_code"] or "",
            home_before=h0, away_before=w0, home_after=h1, away_after=w1,
        ))

    home_final, away_final = to_home_away(cur_a, cur_b)
    return Timeline(
        events=events, home_club=home_club, away_club=away_club,
        duration=REGULATION + n_ot * OT_LEN, n_ot=n_ot,
        home_final=home_final, away_final=away_final, a_is_home=a_is_home,
    )
