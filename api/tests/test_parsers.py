import json

from conftest import load_fixture

from ingest.sources import euroleague as el


def test_normalize_person_code():
    # boxscore/people codes: trim only, never stripped
    assert el.normalize_person_code("006590") == "006590"
    assert el.normalize_person_code("  006590 ") == "006590"
    assert el.normalize_person_code("TGB") == "TGB"
    assert el.normalize_person_code(None) == ""
    assert el.normalize_person_code("          ") == ""


def test_normalize_pbp_player_id():
    # PBP prefixes every person code with 'P' — numeric and legacy alike
    assert el.normalize_pbp_player_id("P007200   ") == "007200"
    assert el.normalize_pbp_player_id("PTGB      ") == "TGB"    # Llull
    assert el.normalize_pbp_player_id("PLCZ") == "LCZ"          # Motiejunas
    assert el.normalize_pbp_player_id("CO_A") == "CO_A"         # coach pseudo-code
    assert el.normalize_pbp_player_id("P") == "P"
    assert el.normalize_pbp_player_id(None) == ""


def test_parse_seasons():
    rows = el.parse_seasons(load_fixture("seasons.json")["data"])
    assert len(rows) == 3
    by_code = {r["code"]: r for r in rows}
    assert by_code["E2026"]["year"] == 2026
    assert by_code["E2026"]["winner_club_code"] is None
    assert by_code["E2000"]["winner_club_code"] == "VIR"
    assert by_code["E2025"]["alias"] == "2025-26"


def test_parse_games():
    rows = el.parse_games(load_fixture("games.json")["data"], "E2025")
    assert len(rows) == 2
    g = next(r for r in rows if r["game_code"] == 406)
    assert g["season_code"] == "E2025"
    assert g["played"] == 1
    assert g["home_club_code"] == "OLY" and g["home_score"] == 92
    assert g["away_club_code"] == "MAD" and g["away_score"] == 85
    assert g["winner_club_code"] == "OLY"
    assert g["phase_type_code"] == "FF"
    partials = json.loads(g["home_partials"])
    assert partials["partials1"] == 19 and partials["partials4"] == 31


def test_parse_boxscore():
    rows = el.parse_boxscore(load_fixture("stats.json"), "IST", "ZAL")
    # 3 players + team + total per side (trimmed fixture)
    assert len(rows) == 10
    players = [r for r in rows if r["entry_type"] == "player"]
    assert len(players) == 6
    beaubois = next(r for r in players if r["player_name"] == "BEAUBOIS, RODRIGUE")
    assert beaubois["player_code"] == "006590"
    assert beaubois["is_home"] == 1 and beaubois["club_code"] == "IST"
    assert beaubois["start_five"] == 0
    home_total = next(r for r in rows if r["entry_type"] == "total" and r["is_home"] == 1)
    assert home_total["player_code"] == ""
    assert home_total["points"] > 0
    assert isinstance(home_total["points"], int)
    # team row = team-attributed stats (e.g. team rebounds), not club identity
    home_team = next(r for r in rows if r["entry_type"] == "team" and r["is_home"] == 1)
    assert home_team["valuation"] == 4


def test_parse_boxscore_empty_doc():
    assert el.parse_boxscore({}, "AAA", "BBB") == []
    assert el.parse_boxscore(None, "AAA", "BBB") == []


def test_parse_pbp():
    rows, live = el.parse_pbp(load_fixture("pbp.json"))
    assert not live
    assert rows
    assert {r["quarter"] for r in rows} == {1, 2, 3, 4}
    begin = next(r for r in rows if r["play_type"] == "BP")
    assert begin["team_code"] == "" and begin["player_code"] == ""
    fgm = next(r for r in rows if r["play_type"] == "2FGM")
    assert fgm["team_code"] == "IST"
    assert fgm["player_code"] == "014102"  # from 'P014102   ' (JONES, KAI)
    assert fgm["points_a"] == 2
    subs = [r for r in rows if r["play_type"] in ("IN", "OUT")]
    assert subs, "fixture must contain substitution events for phase 2"


def test_parse_pbp_missing():
    assert el.parse_pbp(None) == ([], False)
    empty = {"Live": False, "FirstQuarter": [], "SecondQuarter": [],
             "ThirdQuarter": [], "ForthQuarter": [], "ExtraTime": []}
    rows, live = el.parse_pbp(empty)
    assert rows == [] and live is False


def test_parse_people():
    rows = el.parse_people(load_fixture("people.json")["data"])
    assert len(rows) == 3
    player = next(r for r in rows if r["type_name"] == "Player")
    assert player["type_code"] == "J"
    assert player["person_code"]
    assert player["club_code"]
    coach = next(r for r in rows if r["type_name"] == "Assitant coach")
    assert coach["person_code"] == "000406"
    assert coach["country_code"] == "GRE"
