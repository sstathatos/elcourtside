"""PIR — the official Euroleague Performance Index Rating.

(PTS + REB + AST + STL + BLK + fouls drawn)
− (missed FG + missed FT + TO + shots blocked + fouls committed)

Computed from our boxscore_lines columns; the API's own `valuation` column
is kept as ground truth and cross-checked by --validate, never served.
"""

from __future__ import annotations


def compute_pir(line: dict) -> int:
    def v(key: str) -> int:
        return line[key] or 0

    positive = (v("points") + v("reb_total") + v("assists") + v("steals")
                + v("blocks_favour") + v("fouls_received"))
    missed_fg = (v("fg2a") - v("fg2m")) + (v("fg3a") - v("fg3m"))
    missed_ft = v("fta") - v("ftm")
    negative = (missed_fg + missed_ft + v("turnovers")
                + v("blocks_against") + v("fouls_committed"))
    return positive - negative
