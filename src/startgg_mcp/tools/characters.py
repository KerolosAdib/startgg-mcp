from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from ..common import READ_ONLY, Limit, get_db, like_pattern, rate, run
from ..config import DEFAULT_LIMIT, SMALL_SAMPLE_GAMES
from ..resolve import resolve_game

MATCHUP_NOTE = (
    "Based only on games where the organizer reported characters. "
    "Mirror matches are excluded."
)


def register(mcp: MCPServer) -> None:
    """Register the character tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_character_matchups(
        game: Annotated[str, Field(description="Game name or ID, e.g. 'Street Fighter 6'.")],
        ctx: Context,
        character: Annotated[
            str | None,
            Field(description="Only show this character's matchups. Leave empty for the most-played matchups."),
        ] = None,
        min_games: Annotated[
            int, Field(ge=1, description="Leave out matchups with fewer games than this.")
        ] = SMALL_SAMPLE_GAMES,
        limit: Limit = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Character vs character win rates in a game, from reported character picks.
        With a character, lists that character's win rate against each opponent;
        without one, lists the most-played matchups."""
        db = get_db(ctx)
        found_game = resolve_game(db, game)
        if found_game is None:
            raise ToolError("A game is required. Call list_games for the names.")
        name = character.strip() if character and character.strip() else None

        rows = run(
            db,
            """
            SELECT a.character_name AS character, b.character_name AS opponent,
                   count(*) AS games,
                   count(*) FILTER (WHERE sg.winnerid = a.entrantid) AS wins
            FROM startgg_set_game_selections a
            JOIN startgg_set_game_selections b
              ON b.set_game_id = a.set_game_id AND b.entrantid <> a.entrantid
            JOIN startgg_set_games sg ON sg.id = a.set_game_id
            JOIN startgg_sets s ON s.setid = sg.setid
            JOIN startgg_events e ON e.eventid = s.eventid
            WHERE e.videogameid = :game
              AND a.character_name <> b.character_name
              AND (
                  (CAST(:character AS text) IS NULL AND a.character_name < b.character_name)
                  OR lower(a.character_name) = lower(:character)
              )
            GROUP BY a.character_name, b.character_name
            HAVING count(*) >= :min_games
            ORDER BY games DESC, character, opponent
            LIMIT :limit
            """,
            {"game": found_game.id, "character": name, "min_games": min_games, "limit": limit},
        )

        matchups = [
            {
                "character": r["character"],
                "opponent": r["opponent"],
                "games": r["games"],
                "wins": r["wins"],
                "losses": r["games"] - r["wins"],
                "win_rate": rate(r["wins"], r["games"]),
            }
            for r in rows
        ]
        result: dict[str, Any] = {
            "status": "ok",
            "game": found_game.name,
            "character": name,
            "min_games": min_games,
            "note": MATCHUP_NOTE,
            "matchups": matchups,
        }
        if matchups:
            subject = f"{matchups[0]['character']}'s matchups" if name else "Most-played matchups"
            result["summary"] = f"{subject} in {found_game.name} with at least {min_games} games: {len(matchups)} found."
            return result

        if name:
            # Explain why nothing came back: unknown name, or too few games
            known = run(
                db,
                """
                SELECT sel.character_name AS character, count(*) AS games
                FROM startgg_set_game_selections sel
                JOIN startgg_set_games sg ON sg.id = sel.set_game_id
                JOIN startgg_sets s ON s.setid = sg.setid
                JOIN startgg_events e ON e.eventid = s.eventid
                WHERE e.videogameid = :game
                  AND sel.character_name ILIKE '%' || :pattern || '%'
                GROUP BY sel.character_name
                ORDER BY games DESC
                LIMIT 10
                """,
                {"game": found_game.id, "pattern": like_pattern(name)},
            )
            exact = [k for k in known if k["character"].lower() == name.lower()]
            if exact:
                result["summary"] = (
                    f"{exact[0]['character']} has {exact[0]['games']} reported games in {found_game.name}, "
                    f"but no matchup reaches {min_games} games. Try a lower min_games."
                )
            elif known:
                result["summary"] = f"No character named '{name}' in {found_game.name}."
                result["similar_characters"] = [k["character"] for k in known]
            else:
                result["summary"] = f"No character named '{name}' has reported games in {found_game.name}."
        else:
            result["summary"] = (
                f"No matchup in {found_game.name} has at least {min_games} reported games. "
                "Try a lower min_games."
            )
        return result
