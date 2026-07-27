from metrics.timeline import build_timeline


def ev(q, n, pt, team="", player="", minute=None, marker=None, a=None, b=None):
    return {"quarter": q, "play_number": n, "play_type": pt, "team_code": team,
            "player_code": player, "minute": minute, "marker_time": marker,
            "points_a": a, "points_b": b}


def test_clock_math_regulation_and_ot():
    tl = build_timeline([
        ev(1, 1, "BP"),
        ev(1, 2, "2FGM", "H", "p1", marker="09:00", a=2),      # 60s in
        ev(2, 3, "2FGM", "H", "p1", marker="10:00", a=4),      # start of Q2 = 600
        ev(4, 4, "EG"),                                         # end of Q4 = 2400
        ev(5, 5, "2FGM", "H", "p1", minute=42, marker="03:30", a=6),  # OT1
        ev(5, 6, "3FGM", "H", "p1", minute=47, marker="04:00", a=9),  # OT2
    ], "H", "A")
    t = [e.abs_s for e in tl.events]
    assert t[0] == 0.0
    assert t[1] == 60.0
    assert t[2] == 600.0
    assert t[3] == 2400.0
    assert t[4] == 2400.0 + 90.0     # OT1, 1:30 elapsed
    assert t[5] == 2700.0 + 60.0     # OT2, 1:00 elapsed
    assert tl.n_ot == 2
    assert tl.duration == 3000.0


def test_monotonic_clamp_on_clock_glitch():
    tl = build_timeline([
        ev(1, 1, "2FGM", "H", "p1", marker="05:00", a=2),   # 300s
        ev(1, 2, "2FGM", "A", "p2", marker="06:00", b=2),   # glitch: earlier clock
    ], "H", "A")
    assert tl.events[1].abs_s == 300.0  # clamped, never goes backwards


def test_score_carry_forward_and_null_means_unchanged():
    tl = build_timeline([
        ev(1, 1, "2FGM", "H", "p1", marker="09:00", a=2),
        ev(1, 2, "TO", marker="08:00"),                       # no score fields
        ev(1, 3, "3FGM", "A", "p2", marker="07:00", a=2, b=3),
    ], "H", "A")
    e = tl.events[2]
    assert (e.home_before, e.away_before) == (2, 0)
    assert (e.home_after, e.away_after) == (2, 3)
    assert tl.home_final == 2 and tl.away_final == 3


def test_side_inference_when_a_is_away():
    # away club's baskets increment points_a → A is the away side
    tl = build_timeline([
        ev(1, 1, "2FGM", "AWAY", "p1", marker="09:00", a=2),
        ev(1, 2, "2FGM", "HOME", "p2", marker="08:00", a=2, b=2),
        ev(1, 3, "FTM", "AWAY", "p1", marker="07:00", a=3, b=2),
    ], "HOME", "AWAY")
    assert not tl.a_is_home
    assert tl.home_final == 2 and tl.away_final == 3
    assert tl.events[0].delta_away == 2 and tl.events[0].delta_home == 0


def test_deltas():
    tl = build_timeline([
        ev(1, 1, "2FGM", "H", "p1", marker="09:00", a=2),
        ev(1, 2, "FTM", "A", "p2", marker="08:00", a=2, b=1),
    ], "H", "A")
    assert tl.events[0].delta_home == 2
    assert tl.events[1].delta_away == 1
