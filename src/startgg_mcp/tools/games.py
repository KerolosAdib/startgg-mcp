import time
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from ..common import READ_ONLY, get_db, run
from ..config import GAMES_CACHE_SECONDS

# Counting sets and players scans most of the database, and the data only
# changes once a day, so the result is kept for a while
_cache: dict[str, Any] = {"at": 0.0, "result": None}


def register(mcp: MCPServer) -> None:
    """Register the game tools."""

    @mcp.tool(annotations=READ_ONLY)
    def list_games(ctx: Context) -> dict[str, Any]:
        """List the games this server has tournament data for, with how much data each
        has and when it was last updated. Call this first when unsure which games are
        covered or what a game's exact name is."""
        if _cache["result"] is not None and time.monotonic() - _cache["at"] < GAMES_CACHE_SECONDS:
            return _cache["result"]

        rows = run(
            get_db(ctx),
            """
            SELECT g.id, g.name,
                   (SELECT count(*) FROM startgg_events e WHERE e.videogameid = g.id) AS events,
                   (SELECT count(*) FROM startgg_sets s
                    JOIN startgg_events e ON e.eventid = s.eventid
                    WHERE e.videogameid = g.id) AS sets,
                   (SELECT count(DISTINCT ep.playerid) FROM startgg_entrant_players ep
                    JOIN startgg_entrants en ON en.entrantid = ep.entrantid
                    JOIN startgg_events e ON e.eventid = en.eventid
                    WHERE e.videogameid = g.id) AS players,
                   (SELECT to_char(max(e.synced_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD')
                    FROM startgg_events e WHERE e.videogameid = g.id) AS last_synced
            FROM startgg_videogames g
            ORDER BY events DESC, g.name
            """,
        )
        with_data = [r for r in rows if r["events"]]
        result = {
            "summary": f"{len(with_data)} of {len(rows)} games have tournament data.",
            "games": rows,
        }
        _cache.update(at=time.monotonic(), result=result)
        return result
