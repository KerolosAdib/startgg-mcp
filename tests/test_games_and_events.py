import pytest

from startgg_mcp.tools.tournaments import placement_tier, seed_performance

pytestmark = pytest.mark.anyio


async def test_list_games(call):
    result = await call("list_games")
    by_name = {g["name"]: g for g in result["games"]}
    assert by_name["Street Fighter 6"] == {
        "id": 43868,
        "name": "Street Fighter 6",
        "events": 2,
        "sets": 10,
        "players": 8,
        "last_synced": "2026-10-16",
    }
    assert by_name["Skullgirls"]["sets"] == 1
    assert by_name["Tekken 8"]["events"] == 0
    assert result["summary"] == "2 of 3 games have tournament data."


@pytest.mark.parametrize(
    "event",
    [
        "2001",
        "tournament/evo-test-2026/event/street-fighter-6",
        "https://www.start.gg/tournament/evo-test-2026/event/street-fighter-6/overview",
        "https://start.gg/tournament/evo-test-2026",
    ],
)
async def test_event_lookup(call, event):
    result = await call("get_event_results", event=event)
    assert result["event"]["event_id"] == 2001


async def test_event_results(call):
    result = await call("get_event_results", event="2001", limit=3)
    assert result["summary"] == "Street Fighter 6 at Evo Test 2026 (2026-08-01, 8 entrants): won by Kero."
    assert [(s["placement"], s["name"]) for s in result["standings"]] == [(1, "Kero"), (2, "Blaze"), (3, "Nova")]
    assert result["standings"][0]["players"][0]["profile_url"] == "https://www.start.gg/user/a1b2c3d4"
    assert [(u["name"], u["seed"], u["placement"], u["seed_performance"]) for u in result["upsets"]] == [
        ("Kero", 4, 1, 3),
        ("Ash", 8, 5, 1),
    ]


async def test_unknown_event(call):
    result = await call("get_event_results", event="tournament/nope/event/nope")
    assert "No event found" in result["error"]


async def test_search_tournaments(call):
    result = await call("search_tournaments", game="sf6")
    assert [t["name"] for t in result["tournaments"]] == ["Local Weekly 12", "Evo Test 2026"]
    events = result["tournaments"][1]["events"]
    assert events == [
        {
            "event_id": 2001,
            "name": "Street Fighter 6",
            "game": "Street Fighter 6",
            "entrants": 8,
            "event_url": "https://www.start.gg/tournament/evo-test-2026/event/street-fighter-6",
        }
    ]


async def test_search_tournaments_by_name_and_dates(call):
    result = await call("search_tournaments", query="weekly", after="2026-09-20", before="2026-09-20")
    assert [t["name"] for t in result["tournaments"]] == ["Local Weekly 12"]
    result = await call("search_tournaments", before="2025-01-01")
    assert [t["name"] for t in result["tournaments"]] == ["Skullgirls Showdown"]


async def test_character_matchups(call):
    result = await call("get_character_matchups", game="Street Fighter 6", min_games=1)
    assert [(m["character"], m["opponent"], m["games"], m["wins"]) for m in result["matchups"]] == [
        ("Juri", "Ken", 6, 3),
        ("Cammy", "Ken", 2, 1),
    ]


async def test_character_matchups_for_one_character(call):
    result = await call("get_character_matchups", game="sf6", character="ken", min_games=1)
    assert [(m["character"], m["opponent"], m["games"], m["wins"]) for m in result["matchups"]] == [
        ("Ken", "Juri", 6, 3),
        ("Ken", "Cammy", 2, 1),
    ]


async def test_character_matchups_below_min_games(call):
    result = await call("get_character_matchups", game="sf6", character="Juri")
    assert result["matchups"] == []
    assert "no matchup reaches 20 games" in result["summary"]


async def test_character_matchups_unknown_character(call):
    result = await call("get_character_matchups", game="sf6", character="Jur", min_games=1)
    assert result["similar_characters"] == ["Juri"]


def test_placement_tiers():
    placements = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65]
    assert [placement_tier(p) for p in placements] == list(range(len(placements)))
    assert placement_tier(6) == placement_tier(5)
    assert placement_tier(12) == placement_tier(9)
    assert seed_performance(seed=4, placement=1) == 3
    assert seed_performance(seed=1, placement=2) == -1
