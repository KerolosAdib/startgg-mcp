import pytest

from startgg_mcp.links import slug_from_url, startgg_url

pytestmark = pytest.mark.anyio

TOOLS = {
    "list_games",
    "search_players",
    "get_player_profile",
    "get_player_characters",
    "get_head_to_head",
    "get_character_matchups",
    "search_tournaments",
    "get_event_results",
}


async def test_tools_are_listed_and_read_only(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for tool in tools:
        assert tool.annotations.read_only_hint is True
        assert "ctx" not in tool.input_schema.get("properties", {})
        assert tool.description


async def test_instructions_are_sent(client):
    assert "Gamertags are not unique" in client.instructions


async def test_limit_is_validated(call):
    result = await call("search_players", query="kero", limit=1000)
    assert "error" in result


def test_links():
    assert startgg_url("user/a1b2c3d4") == "https://www.start.gg/user/a1b2c3d4"
    assert startgg_url(None) is None
    assert slug_from_url("https://www.start.gg/tournament/evo/event/sf6/brackets/1/2") == "tournament/evo/event/sf6"
    assert slug_from_url("start.gg/tournament/evo") == "tournament/evo"
