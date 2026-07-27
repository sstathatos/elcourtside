"""Largest lead per club, and blown leads (max lead held by the eventual
loser). A tie game has no leader; lead is measured after every score."""

from __future__ import annotations

from dataclasses import dataclass

from metrics.timeline import Timeline


@dataclass
class LeadStats:
    max_lead: dict[str, int]      # club -> biggest lead held
    loser: str | None             # None on a tie (shouldn't happen in a final game)
    blown_lead: int               # loser's max lead, 0 if none


def compute_leads(timeline: Timeline) -> LeadStats:
    max_home = max_away = 0
    for e in timeline.events:
        margin = e.home_after - e.away_after
        max_home = max(max_home, margin)
        max_away = max(max_away, -margin)
    final = timeline.home_final - timeline.away_final
    if final > 0:
        loser = timeline.away_club
        blown = max_away
    elif final < 0:
        loser = timeline.home_club
        blown = max_home
    else:
        loser, blown = None, 0
    return LeadStats(
        max_lead={timeline.home_club: max_home, timeline.away_club: max_away},
        loser=loser,
        blown_lead=blown,
    )
