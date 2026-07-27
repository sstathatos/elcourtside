"""Unit tests for plusminus, clutch, runs, leads, pir, possessions, standings
on small hand-computed scenarios."""

import pytest

from conftest import load_fixture

from metrics.clutch import compute_clutch
from metrics.leads import compute_leads
from metrics.lineups import track_lineups
from metrics.pir import compute_pir
from metrics.plusminus import compute_plus_minus
from metrics.possessions import per_100, player_poss_share, team_possessions
from metrics.runs import max_runs
from metrics.standings import compute_standings
from metrics.timeline import build_timeline
from ingest.sources.euroleague import parse_boxscore


def ev(q, n, pt, team="", player="", minute=None, marker=None, a=None, b=None):
    return {"quarter": q, "play_number": n, "play_type": pt, "team_code": team,
            "player_code": player, "minute": minute, "marker_time": marker,
            "points_a": a, "points_b": b}


H = {"h1", "h2", "h3", "h4", "h5"}
A = {"a1", "a2", "a3", "a4", "a5"}


def test_plus_minus_hand_computed():
    tl = build_timeline([
        ev(1, 1, "2FGM", "H", "h1", marker="09:00", a=2),   # starters: H +2
        ev(1, 2, "OUT", "H", "h1", marker="05:00"),
        ev(1, 3, "IN", "H", "h6", marker="05:00"),
        ev(1, 4, "3FGM", "A", "a1", marker="04:00", a=2, b=3),  # h6 in, h1 out
    ], "H", "A")
    lu = track_lineups(tl, set(H), set(A))
    pm = compute_plus_minus(tl, lu)
    assert pm["h1"] == 2
    assert pm["h6"] == -3
    assert pm["h2"] == 2 - 3 == -1
    assert pm["a1"] == -2 + 3 == 1


def test_clutch_window_and_margin():
    # clutch window opens at abs 2100 (Q4 05:00); margin escapes 5 mid-window
    tl = build_timeline([
        ev(3, 1, "2FGM", "H", "h1", marker="00:30", a=50, b=50),  # 50-50 heading to Q4
        ev(4, 2, "2FGM", "H", "h1", marker="04:00", a=52, b=50),  # before: tied → clutch
        ev(4, 3, "3FGM", "H", "h2", marker="03:00", a=55, b=50),  # before: +2 → clutch
        ev(4, 4, "2FGM", "H", "h1", marker="02:00", a=57, b=50),  # before: +5 → clutch
        ev(4, 5, "2FGM", "H", "h1", marker="01:00", a=59, b=50),  # before: +7 → NOT clutch
    ], "H", "A")
    lu = track_lineups(tl, set(H), set(A))
    st = compute_clutch(tl, lu)
    assert st.player_points["h1"] == 2 + 2          # 04:00 and 02:00 baskets
    assert st.player_points["h2"] == 3
    assert st.home_pts_for == 7 and st.away_pts_for == 0
    # clutch seconds: [2100,2160) margin 0 + [2160,2220) margin 2 +
    # [2220,2280) margin 5 = 180 s; margins 7 and 9 after that are excluded
    assert st.player_seconds["h1"] == pytest.approx(180.0)
    assert st.game_seconds == pytest.approx(180.0)


def test_runs():
    tl = build_timeline([
        ev(1, 1, "2FGM", "H", "h1", marker="09:00", a=2),
        ev(1, 2, "2FGM", "H", "h1", marker="08:00", a=4),
        ev(1, 3, "FTM", "H", "h2", marker="07:30", a=5),
        ev(1, 4, "3FGM", "A", "a1", marker="07:00", a=5, b=3),
        ev(1, 5, "2FGM", "H", "h1", marker="06:00", a=7, b=3),
    ], "H", "A")
    best = max_runs(tl)
    assert best["H"].points == 5            # 5-0 run to open, broken by the 3
    assert best["H"].start_s == 60.0 and best["H"].end_s == 150.0
    assert best["A"].points == 3


def test_leads_and_blown_lead():
    tl = build_timeline([
        ev(1, 1, "3FGM", "A", "a1", marker="09:00", b=3),
        ev(1, 2, "3FGM", "A", "a1", marker="08:00", b=6),   # away up 6
        ev(4, 3, "2FGM", "H", "h1", marker="01:00", a=7, b=6),  # home wins 7-6
    ], "H", "A")
    st = compute_leads(tl)
    assert st.max_lead["A"] == 6
    assert st.max_lead["H"] == 1
    assert st.loser == "A" and st.blown_lead == 6


def test_pir_matches_official_valuation_on_fixture():
    rows = parse_boxscore(load_fixture("stats.json"), "IST", "ZAL")
    stats_doc = load_fixture("stats.json")
    official = {}
    for side in ("local", "road"):
        for p in stats_doc[side]["players"]:
            official[p["player"]["person"]["code"].strip()] = int(p["stats"]["valuation"])
    for r in rows:
        if r["entry_type"] == "player":
            assert compute_pir(r) == official[r["player_code"]], r["player_name"]


def test_possessions_formula():
    total = {"fg2a": 40, "fg3a": 25, "fta": 20, "reb_off": 10, "turnovers": 12}
    poss = team_possessions(total)
    assert poss == pytest.approx(40 + 25 + 0.44 * 20 - 10 + 12)
    # player on court half the game sees half the possessions
    assert player_poss_share(poss, 1200.0, 2400.0) == pytest.approx(poss / 2)
    assert player_poss_share(poss, None, 2400.0) == 0.0
    assert per_100(5, 0) is None
    assert per_100(5, 50.0) == pytest.approx(10.0)


def _g(h, a, hs, as_):
    return {"home_club_code": h, "home_club_name": h, "home_score": hs,
            "away_club_code": a, "away_club_name": a, "away_score": as_}


def test_standings_tiebreak_head_to_head():
    # X and Y both 2-1; Y beat X head-to-head → Y ranks above X despite
    # X's better overall point diff. Z 1-2, W 1-2, Z beat W.
    games = [
        _g("X", "W", 100, 60),   # X huge diff
        _g("Y", "X", 80, 78),    # h2h: Y > X
        _g("X", "Z", 90, 80),
        _g("Y", "Z", 70, 65),
        _g("W", "Y", 75, 70),
        _g("Z", "W", 80, 70),
    ]
    table = compute_standings(games)
    order = [r.club_code for r in table]
    assert order[0] == "Y" and order[1] == "X"      # h2h breaks the 2-1 tie
    assert order[2] == "Z" and order[3] == "W"      # h2h breaks the 1-2 tie
    assert [r.rank for r in table] == [1, 2, 3, 4]
    x = next(r for r in table if r.club_code == "X")
    assert (x.wins, x.losses) == (2, 1)
    assert x.points_for == 100 + 78 + 90
