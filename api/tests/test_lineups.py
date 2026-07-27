from metrics.lineups import track_lineups
from metrics.timeline import build_timeline


def ev(q, n, pt, team="", player="", minute=None, marker=None, a=None, b=None):
    return {"quarter": q, "play_number": n, "play_type": pt, "team_code": team,
            "player_code": player, "minute": minute, "marker_time": marker,
            "points_a": a, "points_b": b}


H_START = {"h1", "h2", "h3", "h4", "h5"}
A_START = {"a1", "a2", "a3", "a4", "a5"}


def test_simple_sub_intervals_and_seconds():
    tl = build_timeline([
        ev(1, 1, "BP"),
        ev(1, 2, "OUT", "H", "h1", marker="05:00"),
        ev(1, 3, "IN", "H", "h6", marker="05:00"),
    ], "H", "A")
    lu = track_lineups(tl, set(H_START), set(A_START))
    assert lu.seconds["h1"] == 300.0
    assert lu.seconds["h6"] == 2400.0 - 300.0
    assert lu.seconds["h2"] == 2400.0
    assert not lu.anomalies


def test_in_before_out_at_same_clock_is_reordered():
    tl = build_timeline([
        ev(1, 1, "IN", "H", "h6", marker="05:00"),
        ev(1, 2, "OUT", "H", "h1", marker="05:00"),
    ], "H", "A")
    lu = track_lineups(tl, set(H_START), set(A_START))
    assert lu.seconds["h1"] == 300.0
    assert lu.seconds["h6"] == 2100.0
    assert not [a for a in lu.anomalies if "on court" in a]


def test_interleaved_clubs_same_clock():
    tl = build_timeline([
        ev(1, 1, "IN", "H", "h6", marker="04:00"),
        ev(1, 2, "IN", "A", "a6", marker="04:00"),
        ev(1, 3, "OUT", "H", "h1", marker="04:00"),
        ev(1, 4, "OUT", "A", "a1", marker="04:00"),
    ], "H", "A")
    lu = track_lineups(tl, set(H_START), set(A_START))
    assert lu.seconds["h1"] == 360.0 and lu.seconds["a1"] == 360.0
    assert lu.seconds["h6"] == 2040.0 and lu.seconds["a6"] == 2040.0
    assert not [a for a in lu.anomalies if "on court" in a]


def test_out_without_in_assumes_period_start():
    tl = build_timeline([
        ev(2, 1, "OUT", "H", "h7", marker="05:00"),  # never entered; Q2 starts at 600
    ], "H", "A")
    lu = track_lineups(tl, set(H_START), set(A_START))
    assert lu.seconds["h7"] == 300.0  # 600 → 900
    assert any("OUT without IN" in a for a in lu.anomalies)


def test_double_in_is_anomaly_not_crash():
    tl = build_timeline([
        ev(1, 1, "IN", "H", "h1", marker="05:00"),  # already a starter
    ], "H", "A")
    lu = track_lineups(tl, set(H_START), set(A_START))
    assert lu.seconds["h1"] == 2400.0
    assert any("double IN" in a for a in lu.anomalies)


def test_states_track_current_five():
    tl = build_timeline([
        ev(1, 1, "2FGM", "H", "h1", marker="08:00", a=2),
        ev(1, 2, "OUT", "H", "h1", marker="05:00"),
        ev(1, 3, "IN", "H", "h6", marker="05:00"),
        ev(1, 4, "2FGM", "H", "h6", marker="03:00", a=4),
    ], "H", "A")
    lu = track_lineups(tl, set(H_START), set(A_START))
    on_home_first, _ = lu.states[0]
    on_home_last, _ = lu.states[3]
    assert "h1" in on_home_first and "h6" not in on_home_first
    assert "h6" in on_home_last and "h1" not in on_home_last
