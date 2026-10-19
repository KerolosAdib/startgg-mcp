"""Turning the game and player names a user gives into database IDs.

Gamertags are not unique on start.gg, so a player lookup either finds exactly
one player, or returns a response for the model to show the user: the
candidates when several players share the tag, or similar tags when none match.
"""

import re
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from .common import id_list, like_pattern, run, split_list
from .config import MAX_CANDIDATES
from .db import Database
from .links import startgg_url


@dataclass
class Game:
    id: int
    name: str


@dataclass
class PlayerLookup:
    """Either the resolved player, or a response to return to the model as-is."""

    player: dict[str, Any] | None = None
    response: dict[str, Any] | None = None


def _acronym(name: str) -> str:
    """'Street Fighter 6' -> 'sf6', 'Tekken 8' -> 't8'."""
    words = re.findall(r"[A-Za-z]+|\d+", name)
    return "".join(w if w.isdigit() else w[0] for w in words).lower()


def resolve_game(db: Database, game: str | None) -> Game | None:
    """Find a game by ID, exact name, acronym or part of its name.
    Returns None when no game was given."""
    if game is None or not game.strip():
        return None
    wanted = game.strip().lower()
    games = [Game(r["id"], r["name"]) for r in run(db, "SELECT id, name FROM startgg_videogames ORDER BY name")]

    for check in (
        lambda g: str(g.id) == wanted,
        lambda g: g.name.lower() == wanted,
        lambda g: _acronym(g.name) == wanted.replace(" ", ""),
    ):
        found = [g for g in games if check(g)]
        if len(found) == 1:
            return found[0]

    partial = [g for g in games if wanted in g.name.lower()]
    if len(partial) == 1:
        return partial[0]

    names = ", ".join(g.name for g in (partial or games))
    if partial:
        raise ToolError(f"'{game}' matches several games: {names}. Use the full name.")
    raise ToolError(f"No data for a game called '{game}'. Games covered: {names}.")


def describe_players(db: Database, ids: list[int]) -> list[dict[str, Any]]:
    """Details that tell players with the same tag apart, most active first."""
    if not ids:
        return []
    rows = run(
        db,
        """
        WITH ids AS (
            SELECT CAST(x AS integer) AS playerid
            FROM unnest(string_to_array(:ids, ',')) AS x
        ),
        activity AS (
            SELECT ep.playerid,
                   count(DISTINCT en.eventid) AS events,
                   to_char(max(e.startdate), 'YYYY-MM-DD') AS last_seen,
                   string_agg(DISTINCT g.name, chr(31)) AS games
            FROM ids
            JOIN startgg_entrant_players ep ON ep.playerid = ids.playerid
            JOIN startgg_entrants en ON en.entrantid = ep.entrantid
            JOIN startgg_events e ON e.eventid = en.eventid
            JOIN startgg_videogames g ON g.id = e.videogameid
            GROUP BY ep.playerid
        ),
        picks AS (
            SELECT DISTINCT ON (ep.playerid) ep.playerid, sel.character_name
            FROM ids
            JOIN startgg_entrant_players ep ON ep.playerid = ids.playerid
            JOIN startgg_set_game_selections sel ON sel.entrantid = ep.entrantid
            GROUP BY ep.playerid, sel.character_name
            ORDER BY ep.playerid, count(*) DESC, sel.character_name
        )
        SELECT p.playerid AS id, p.gamertag, p.slug,
               coalesce(a.events, 0) AS events, a.last_seen, a.games,
               k.character_name AS top_character
        FROM ids
        JOIN startgg_players p ON p.playerid = ids.playerid
        LEFT JOIN activity a ON a.playerid = p.playerid
        LEFT JOIN picks k ON k.playerid = p.playerid
        ORDER BY events DESC, p.playerid
        """,
        {"ids": id_list(ids)},
    )
    return [
        {
            "id": r["id"],
            "gamertag": r["gamertag"],
            "profile_url": startgg_url(r["slug"]),
            "games": split_list(r["games"]),
            "events": r["events"],
            "last_seen": r["last_seen"],
            "top_character": r["top_character"],
        }
        for r in rows
    ]


def _in_game(alias: str) -> str:
    """SQL condition: the player has at least one entry in :game (or no game given)."""
    return f"""(CAST(:game AS bigint) IS NULL OR EXISTS (
        SELECT 1 FROM startgg_entrant_players ep
        JOIN startgg_entrants en ON en.entrantid = ep.entrantid
        JOIN startgg_events e ON e.eventid = en.eventid
        WHERE ep.playerid = {alias}.playerid AND e.videogameid = :game))"""


def search_player_ids(db: Database, text: str, game: Game | None, limit: int) -> list[int]:
    """IDs of players whose tag contains the text, exact matches and shorter tags first."""
    rows = run(
        db,
        f"""
        SELECT p.playerid
        FROM startgg_players p
        WHERE p.gamertag ILIKE '%' || :pattern || '%' AND {_in_game('p')}
        ORDER BY lower(p.gamertag) = lower(:text) DESC, length(p.gamertag), p.playerid
        LIMIT :limit
        """,
        {"pattern": like_pattern(text), "text": text, "game": game.id if game else None, "limit": limit},
    )
    return [r["playerid"] for r in rows]


def _player(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row["id"], "gamertag": row["gamertag"], "profile_url": startgg_url(row["slug"])}


def resolve_player(db: Database, player: str, game: Game | None) -> PlayerLookup:
    """Find exactly one player by ID or gamertag (case-insensitive)."""
    text = player.strip()
    where_game = f" in {game.name}" if game else ""

    if text.isdigit():
        rows = run(
            db,
            "SELECT playerid AS id, gamertag, slug FROM startgg_players WHERE playerid = :id",
            {"id": int(text)},
        )
        if not rows:
            raise ToolError(f"No player with ID {text}.")
        return PlayerLookup(player=_player(rows[0]))

    rows = run(
        db,
        f"""
        SELECT p.playerid AS id, p.gamertag, p.slug
        FROM startgg_players p
        WHERE lower(p.gamertag) = lower(:tag) AND {_in_game('p')}
        LIMIT 200
        """,
        {"tag": text, "game": game.id if game else None},
    )

    if len(rows) == 1:
        return PlayerLookup(player=_player(rows[0]))

    if len(rows) > 1:
        candidates = describe_players(db, [r["id"] for r in rows])
        response = {
            "status": "ambiguous",
            "message": (
                f'{len(rows)} players are tagged "{text}"{where_game}. Show these to the user '
                "with their games, activity and profile links, and ask which one they mean. "
                "Then call again with that player's id. Do not pick one yourself."
            ),
            "candidates": candidates[:MAX_CANDIDATES],
        }
        if len(candidates) > MAX_CANDIDATES:
            response["more_candidates"] = len(candidates) - MAX_CANDIDATES
        return PlayerLookup(response=response)

    suggestions = describe_players(db, search_player_ids(db, text, game, MAX_CANDIDATES))
    return PlayerLookup(
        response={
            "status": "not_found",
            "message": (
                f'No player is tagged "{text}"{where_game}. '
                + (
                    "Similar tags are listed; ask the user whether one of them is who they meant."
                    if suggestions
                    else "Check the spelling, or try search_players with part of the tag."
                )
            ),
            "suggestions": suggestions,
        }
    )
