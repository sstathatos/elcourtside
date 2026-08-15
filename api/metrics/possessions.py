"""Possession estimates and fouls-drawn rates (boxscore-based)."""

from __future__ import annotations


def team_possessions(total_line: dict) -> float:
    fga = (total_line["fg2a"] or 0) + (total_line["fg3a"] or 0)
    fta = total_line["fta"] or 0
    orb = total_line["reb_off"] or 0
    tov = total_line["turnovers"] or 0
    return fga + 0.44 * fta - orb + tov


def player_poss_share(team_poss: float, seconds_played: float | None,
                      game_duration: float) -> float:
    if not seconds_played or game_duration <= 0:
        return 0.0
    return team_poss * (seconds_played / game_duration)


def per_100(count: int | float, possessions: float) -> float | None:
    if possessions <= 0:
        return None
    return 100.0 * count / possessions
