from datetime import date
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from ..common import (
    READ_ONLY,
    GameArg,
    Limit,
    get_db,
    id_list,
    like_pattern,
    run,
    split_list,
)
from ..config import DEFAULT_LIMIT
from ..db import Database
from ..links import slug_from_url, startgg_url
from ..resolve import resolve_game

UPSETS_SHOWN = 5
FIELD_SEP = "\x1e"  # chr(30): separates a player's id, tag and slug in SQL lists


def placement_tier(position: int) -> int:
    """Index of the double-elimination placement a seed or placing falls in:
    1st -> 0, 2nd -> 1, 3rd -> 2, 4th -> 3, 5th-6th -> 4, 7th-8th -> 5, 9th-12th -> 6, ..."""
    if position <= 2:
        return max(position - 1, 0)
    k = (position - 1).bit_length() - 1
    return 2 * k + (1 if position - 1 >= 1.5 * 2**k else 0)


def seed_performance(seed: int, placement: int) -> int:
    """Seed performance rating: how many placement tiers above (positive) or below
    (negative) their seed an entrant finished."""
    return placement_tier(seed) - placement_tier(placement)


def _players(packed: str | None) -> list[dict[str, Any]]:
    players = []
    for item in split_list(packed):
        pid, tag, slug = item.split(FIELD_SEP)
        players.append({"id": int(pid), "gamertag": tag, "profile_url": startgg_url(slug or None)})
    return players


def _find_event(db: Database, event: str) -> dict[str, Any] | list[dict[str, Any]]:
    """The event row for an ID, slug or URL; or the tournament's events when the
    value names a tournament with several events."""
    columns = """e.eventid AS id, e.eventname, e.slug, e.numentrants,
                 to_char(coalesce(e.startdate, t.startdate), 'YYYY-MM-DD') AS date,
                 t.tournamentname, t.slug AS tournament_slug, g.name AS game
          FROM startgg_events e
          JOIN startgg_tournaments t ON t.tournamentid = e.tournamentid
          JOIN startgg_videogames g ON g.id = e.videogameid"""
    text = event.strip()
    if text.isdigit():
        rows = run(db, f"SELECT {columns} WHERE e.eventid = :id", {"id": int(text)})
    else:
        slug = slug_from_url(text)
        rows = run(db, f"SELECT {columns} WHERE e.slug = :slug", {"slug": slug})
        if not rows and slug.startswith("tournament/"):
            tournament = "/".join(slug.split("/")[:2])
            rows = run(
                db,
                f"SELECT {columns} WHERE t.slug = :slug ORDER BY e.numentrants DESC NULLS LAST",
                {"slug": tournament},
            )
            if len(rows) > 1:
                return rows
    if not rows:
        raise ToolError(f"No event found for '{event}'. Use an event ID, or a start.gg event URL.")
    return rows[0]


def register(mcp: MCPServer) -> None:
    """Register the tournament tools."""

    @mcp.tool(annotations=READ_ONLY)
    def search_tournaments(
        ctx: Context,
        query: Annotated[str | None, Field(description="Part of the tournament name.")] = None,
        game: GameArg = None,
        after: Annotated[date | None, Field(description="Only tournaments on or after this date.")] = None,
        before: Annotated[date | None, Field(description="Only tournaments on or before this date.")] = None,
        limit: Limit = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Find tournaments by name, game and date range, newest first. Each tournament
        lists its events with entrant counts, event IDs and start.gg links; pass an
        event ID to get_event_results for standings."""
        db = get_db(ctx)
        found_game = resolve_game(db, game)
        game_id = found_game.id if found_game else None
        text = query.strip() if query and query.strip() else None

        tournaments = run(
            db,
            """
            SELECT t.tournamentid AS id, t.tournamentname AS name, t.slug,
                   to_char(t.startdate, 'YYYY-MM-DD') AS date
            FROM startgg_tournaments t
            WHERE (CAST(:pattern AS text) IS NULL OR t.tournamentname ILIKE '%' || :pattern || '%')
              AND (CAST(:after AS date) IS NULL OR t.startdate >= CAST(:after AS date))
              AND (CAST(:before AS date) IS NULL OR t.startdate < CAST(:before AS date) + 1)
              AND EXISTS (
                  SELECT 1 FROM startgg_events e
                  WHERE e.tournamentid = t.tournamentid
                    AND (CAST(:game AS bigint) IS NULL OR e.videogameid = :game)
              )
            ORDER BY t.startdate DESC NULLS LAST, t.tournamentid DESC
            LIMIT :limit
            """,
            {
                "pattern": like_pattern(text) if text else None,
                "after": after.isoformat() if after else None,
                "before": before.isoformat() if before else None,
                "game": game_id,
                "limit": limit,
            },
        )

        events = run(
            db,
            """
            SELECT e.eventid AS id, e.tournamentid, e.eventname AS name, e.slug,
                   e.numentrants AS entrants, g.name AS game
            FROM startgg_events e
            JOIN startgg_videogames g ON g.id = e.videogameid
            WHERE e.tournamentid = ANY(CAST(string_to_array(:ids, ',') AS integer[]))
              AND (CAST(:game AS bigint) IS NULL OR e.videogameid = :game)
            ORDER BY e.numentrants DESC NULLS LAST
            """,
            {"ids": id_list([t["id"] for t in tournaments]) or "0", "game": game_id},
        )

        by_tournament: dict[int, list[dict[str, Any]]] = {}
        for e in events:
            by_tournament.setdefault(e["tournamentid"], []).append(
                {
                    "event_id": e["id"],
                    "name": e["name"],
                    "game": e["game"],
                    "entrants": e["entrants"],
                    "event_url": startgg_url(e["slug"]),
                }
            )
        return {
            "summary": f"{len(tournaments)} tournaments found" + (" (limit reached)" if len(tournaments) == limit else "") + ".",
            "tournaments": [
                {
                    "name": t["name"],
                    "date": t["date"],
                    "tournament_url": startgg_url(t["slug"]),
                    "events": by_tournament.get(t["id"], []),
                }
                for t in tournaments
            ],
        }

    @mcp.tool(annotations=READ_ONLY)
    def get_event_results(
        event: Annotated[str, Field(description="Event ID, or a start.gg event URL or slug.")],
        ctx: Context,
        limit: Limit = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Final standings of one event with each entrant's seed, plus the biggest
        upsets: entrants who finished furthest above their seed, measured as a seed
        performance rating (placement tiers gained)."""
        db = get_db(ctx)
        found = _find_event(db, event)
        if isinstance(found, list):
            return {
                "status": "ambiguous",
                "message": (
                    "That tournament has several events. Ask the user which one they mean, "
                    "then call again with its event_id."
                ),
                "candidates": [
                    {
                        "event_id": e["id"],
                        "name": e["eventname"],
                        "game": e["game"],
                        "entrants": e["numentrants"],
                        "event_url": startgg_url(e["slug"]),
                    }
                    for e in found
                ],
            }

        placings = run(
            db,
            """
            SELECT entrantid, seed_placement AS seed, final_placement AS placement, is_disqualified
            FROM startgg_entrants
            WHERE eventid = :id
            ORDER BY final_placement NULLS LAST, seed_placement NULLS LAST
            """,
            {"id": found["id"]},
        )
        upsets = sorted(
            (
                {**p, "spr": seed_performance(p["seed"], p["placement"])}
                for p in placings
                if p["seed"] and p["placement"] and not p["is_disqualified"]
            ),
            key=lambda p: (-p["spr"], p["placement"]),
        )
        upsets = [u for u in upsets if u["spr"] > 0][:UPSETS_SHOWN]
        shown = placings[:limit]

        names = run(
            db,
            """
            SELECT ep.entrantid,
                   string_agg(CAST(p.playerid AS text) || chr(30) || p.gamertag || chr(30) || coalesce(p.slug, ''),
                              chr(31) ORDER BY p.playerid) AS players
            FROM startgg_entrant_players ep
            JOIN startgg_players p ON p.playerid = ep.playerid
            WHERE ep.entrantid = ANY(CAST(string_to_array(:ids, ',') AS integer[]))
            GROUP BY ep.entrantid
            """,
            {"ids": id_list([p["entrantid"] for p in shown + upsets]) or "0"},
        )
        players_of = {n["entrantid"]: _players(n["players"]) for n in names}

        def entry(p: dict[str, Any]) -> dict[str, Any]:
            players = players_of.get(p["entrantid"], [])
            return {
                "placement": p["placement"],
                "seed": p["seed"],
                "name": " / ".join(pl["gamertag"] for pl in players) or None,
                "players": players,
                "disqualified": bool(p["is_disqualified"]),
            }

        top = shown[0] if shown else None
        winner = entry(top)["name"] if top and top["placement"] == 1 else None
        summary = f"{found['eventname']} at {found['tournamentname']} ({found['date']}, {found['numentrants']} entrants)"
        summary += f": won by {winner}." if winner else "."
        return {
            "status": "ok",
            "event": {
                "event_id": found["id"],
                "name": found["eventname"],
                "tournament": found["tournamentname"],
                "game": found["game"],
                "date": found["date"],
                "entrants": found["numentrants"],
                "event_url": startgg_url(found["slug"]),
                "tournament_url": startgg_url(found["tournament_slug"]),
            },
            "summary": summary,
            "standings": [entry(p) for p in shown],
            "upsets": [{**entry(u), "seed_performance": u["spr"]} for u in upsets],
        }
