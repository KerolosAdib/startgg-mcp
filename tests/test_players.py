import pytest

pytestmark = pytest.mark.anyio


async def test_shared_tag_returns_candidates(call):
    result = await call("get_player_profile", player="Kero")
    assert result["status"] == "ambiguous"
    assert "Do not pick one yourself" in result["message"]
    first, second = result["candidates"]
    assert first == {
        "id": 3001,
        "gamertag": "Kero",
        "profile_url": "https://www.start.gg/user/a1b2c3d4",
        "games": ["Street Fighter 6"],
        "events": 2,
        "last_seen": "2026-09-20",
        "top_character": "Juri",
    }
    assert second["id"] == 3002
    assert second["profile_url"] is None
    assert second["games"] == ["Skullgirls"]


@pytest.mark.parametrize(("game", "player_id"), [("Street Fighter 6", 3001), ("sf6", 3001), ("Skullgirls", 3002)])
async def test_game_narrows_shared_tag(call, game, player_id):
    result = await call("get_player_profile", player="kero", game=game)
    assert result["status"] == "ok"
    assert result["player"]["id"] == player_id


async def test_profile_record(call):
    result = await call("get_player_profile", player="3001", game="Street Fighter 6")
    assert result["record"] == {
        "sets": 8,
        "set_wins": 6,
        "set_losses": 2,
        "set_win_rate": 0.75,
        "games": 24,
        "game_wins": 16,
        "game_losses": 8,
        "game_win_rate": 0.667,
        "dq_sets_excluded": 0,
    }
    assert result["events_entered"] == 2
    best = result["best_placements"][0]
    assert (best["tournament"], best["placement"], best["seed"], best["entrants"]) == ("Evo Test 2026", 1, 4, 8)
    assert best["event_url"] == "https://www.start.gg/tournament/evo-test-2026/event/street-fighter-6"
    assert [r["date"] for r in result["recent_results"]] == ["2026-09-20", "2026-08-01"]


async def test_dq_sets_are_excluded(call):
    result = await call("get_player_profile", player="Ash", game="Street Fighter 6")
    assert result["record"]["sets"] == 1
    assert result["record"]["dq_sets_excluded"] == 1


async def test_unknown_tag_suggests_similar(call):
    result = await call("get_player_profile", player="ker")
    assert result["status"] == "not_found"
    assert {s["gamertag"] for s in result["suggestions"]} == {"Kero", "Kerosene"}


async def test_unknown_tag_without_suggestions(call):
    result = await call("get_player_profile", player="nobody")
    assert result["status"] == "not_found"
    assert result["suggestions"] == []


async def test_unknown_player_id(call):
    result = await call("get_player_profile", player="999")
    assert "No player with ID 999" in result["error"]


async def test_search_players(call):
    result = await call("search_players", query="kero")
    assert [p["gamertag"] for p in result["players"]] == ["Kero", "Kero", "Kerosene"]
    assert result["players"][0]["events"] == 2


async def test_search_players_in_game(call):
    result = await call("search_players", query="kero", game="Skullgirls")
    assert [p["id"] for p in result["players"]] == [3002]


async def test_search_treats_wildcards_literally(call):
    result = await call("search_players", query="%")
    assert result["players"] == []


async def test_player_characters(call):
    result = await call("get_player_characters", player="3001")
    assert result["games_with_character_data"] == 8
    assert result["characters"] == [
        {"character": "Juri", "games": 6, "wins": 3, "losses": 3, "win_rate": 0.5},
        {"character": "Cammy", "games": 2, "wins": 1, "losses": 1, "win_rate": 0.5},
    ]


async def test_player_without_character_data(call):
    result = await call("get_player_characters", player="Nova")
    assert result["characters"] == []
    assert "No character data" in result["summary"]


async def test_head_to_head(call):
    result = await call("get_head_to_head", player_a="Kero", player_b="Blaze", game="Street Fighter 6")
    assert result["status"] == "ok"
    assert (result["sets"], result["player_a_set_wins"], result["player_b_set_wins"]) == (4, 3, 1)
    assert (result["player_a_game_wins"], result["player_b_game_wins"]) == (9, 4)
    latest = result["recent_sets"][0]
    assert (latest["date"], latest["winner"], latest["score"]) == ("2026-09-20", "Kero", "2-0")
    assert [s["score"] for s in result["recent_sets"]] == ["2-0", "3-0", "3-2", "1-2"]


async def test_head_to_head_from_other_side(call):
    result = await call("get_head_to_head", player_a="Blaze", player_b="3001")
    assert (result["player_a_set_wins"], result["player_b_set_wins"]) == (1, 3)
    assert result["recent_sets"][0]["score"] == "0-2"


async def test_head_to_head_with_shared_tag(call):
    result = await call("get_head_to_head", player_a="Kero", player_b="Blaze")
    assert result["status"] == "ambiguous"
    assert result["player_a"]["status"] == "ambiguous"
    assert result["player_b"] == {"status": "ok", "player": result["player_b"]["player"]}


async def test_head_to_head_same_player(call):
    result = await call("get_head_to_head", player_a="3001", player_b="3001")
    assert "same player" in result["error"]


async def test_unknown_game(call):
    result = await call("get_player_profile", player="Blaze", game="Smash")
    assert "No data for a game called 'Smash'" in result["error"]
