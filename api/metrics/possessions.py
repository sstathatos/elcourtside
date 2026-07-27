"""Possession estimates and fouls-drawn rates (boxscore-based).

Team possessions per game use the standard estimator over the team's
*total* boxscore line:  FGA + 0.44·FTA − ORB + TO.

Player-level "possessions available" is the team's possessions scaled by
the player's share of game time (seconds_played / game duration): a player
on court for half the game saw ~half the team's possessions. Fouls drawn
per 100 possessions divides boxscore fouls_received by that availability —
a rate metric that is fair across bench and starter minutes.
"""

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
