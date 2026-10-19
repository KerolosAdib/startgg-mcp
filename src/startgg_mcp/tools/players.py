from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..common import READ_ONLY, GameArg, Limit, PlayerArg, get_db, rate, run
from ..config import DEFAULT_LIMIT, RECENT_RESULTS, TOP_PLACEMENTS
from ..links import startgg_url
from ..resolve import describe_players, resolve_game, resolve_player, search_player_ids


def entrants_cte(name: str, param: str) -> str:
    """CTE of a player's entrant IDs (one per event entered), limited to :game when given."""
    return f"""{name} AS (
        SELECT en.entrantid, en.eventid
        FROM startgg_entrant_players ep
        JOIN startgg_entrants en ON en.entrantid = ep.entrantid
        JOIN startgg_events e ON e.eventid = en.eventid
        WHERE ep.playerid = :{param}
          AND (CAST(:game AS bigint) IS NULL OR e.videogameid = :game)
    )"""


def _result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": row["eventname"],
        "tournament": row["tournamentname"],
        "game": row["game"],
        "date": row["date"],
        "placement": row["placement"],
        "seed": row["seed"],
        "entrants": row["numentrants"],
        "disqualified": bool(row["is_disqualified"]),
        "event_url": startgg_url(row["slug"]),
    }


def register(mcp: MCPServer) -> None:
    """Register the player tools."""

    @mcp.tool(annotations=READ_ONLY)
    def search_players(
        query: str, ctx: Context, game: GameArg = None, limit: Limit = DEFAULT_LIMIT
    ) -> dict[str, Any]:
        """Find players whose gamertag contains the given text. Returns each match with
        its start.gg profile link, games played, events entered, last event date and
        most-picked character, so players with the same tag can be told apart."""
        if not query.strip():
            raise ToolError("Give part of a gamertag to search for.")
        db = get_db(ctx)
        found_game = resolve_game(db, game)
        players = describe_players(db, search_player_ids(db, query.strip(), found_game, limit))
        wanted = query.strip().lower()
        players.sort(key=lambda p: (p["gamertag"].lower() != wanted, -p["events"]))
        where_game = f" in {found_game.name}" if found_game else ""
        return {
            "summary": f'{len(players)} players{where_game} have a tag containing "{query.strip()}".',
            "players": players,
        }

    @mcp.tool(annotations=READ_ONLY)
    def get_player_profile(player: PlayerArg, ctx: Context, game: GameArg = None) -> dict[str, Any]:
        """A player's overall record: sets and games won and lost, events entered, best
        placements and most recent results, each with its start.gg link. If several
        players share the tag, returns candidates instead: show them to the user and
        ask which one they mean."""
        db = get_db(ctx)
        found_game = resolve_game(db, game)
        lookup = resolve_player(db, player, found_game)
        if lookup.response:
            return lookup.response
        who = lookup.player
        params = {"pid": who["id"], "game": found_game.id if found_game else None}

        [record] = run(
            db,
            f"""
            WITH {entrants_cte('mine', 'pid')},
            my_sets AS (
                SELECT s.winnerid, s.hasdq, m.entrantid AS me,
                       s.playeronewins AS my_games, s.playertwowins AS their_games
                FROM mine m JOIN startgg_sets s ON s.entrantoneid = m.entrantid
                UNION ALL
                SELECT s.winnerid, s.hasdq, m.entrantid,
                       s.playertwowins, s.playeronewins
                FROM mine m JOIN startgg_sets s ON s.entranttwoid = m.entrantid
            )
            SELECT count(*) FILTER (WHERE hasdq IS NOT TRUE) AS sets,
                   count(*) FILTER (WHERE hasdq IS NOT TRUE AND winnerid = me) AS set_wins,
                   coalesce(sum(greatest(my_games, 0)) FILTER (WHERE hasdq IS NOT TRUE), 0) AS game_wins,
                   coalesce(sum(greatest(their_games, 0)) FILTER (WHERE hasdq IS NOT TRUE), 0) AS game_losses,
                   count(*) FILTER (WHERE hasdq) AS dq_sets
            FROM my_sets
            """,
            params,
        )

        results = run(
            db,
            f"""
            WITH {entrants_cte('mine', 'pid')}
            SELECT en.final_placement AS placement, en.seed_placement AS seed, en.is_disqualified,
                   e.eventname, e.numentrants, e.slug, t.tournamentname, g.name AS game,
                   to_char(coalesce(e.startdate, t.startdate), 'YYYY-MM-DD') AS date
            FROM mine m
            JOIN startgg_entrants en ON en.entrantid = m.entrantid
            JOIN startgg_events e ON e.eventid = en.eventid
            JOIN startgg_tournaments t ON t.tournamentid = e.tournamentid
            JOIN startgg_videogames g ON g.id = e.videogameid
            """,
            params,
        )

        placed = [r for r in results if r["placement"] is not None]
        best = sorted(placed, key=lambda r: (r["placement"], -(r["numentrants"] or 0)))[:TOP_PLACEMENTS]
        recent = sorted(results, key=lambda r: r["date"] or "", reverse=True)[:RECENT_RESULTS]

        sets, set_wins = record["sets"], record["set_wins"]
        game_wins, game_losses = record["game_wins"], record["game_losses"]
        scope = f" in {found_game.name}" if found_game else ""
        summary = (
            f"{who['gamertag']}{scope}: {set_wins}-{sets - set_wins} in sets, "
            f"{game_wins}-{game_losses} in games, across {len(results)} events."
        )
        return {
            "status": "ok",
            "player": who,
            "game": found_game.name if found_game else None,
            "summary": summary,
            "record": {
                "sets": sets,
                "set_wins": set_wins,
                "set_losses": sets - set_wins,
                "set_win_rate": rate(set_wins, sets),
                "games": game_wins + game_losses,
                "game_wins": game_wins,
                "game_losses": game_losses,
                "game_win_rate": rate(game_wins, game_wins + game_losses),
                "dq_sets_excluded": record["dq_sets"],
            },
            "events_entered": len(results),
            "best_placements": [_result(r) for r in best],
            "recent_results": [_result(r) for r in recent],
        }

    @mcp.tool(annotations=READ_ONLY)
    def get_player_characters(
        player: PlayerArg, ctx: Context, game: GameArg = None, limit: Limit = DEFAULT_LIMIT
    ) -> dict[str, Any]:
        """The characters a player has used, with games played, games won and win rate
        for each. Only covers games where the organizer reported characters. If several
        players share the tag, returns candidates instead: show them to the user and
        ask which one they mean."""
        db = get_db(ctx)
        found_game = resolve_game(db, game)
        lookup = resolve_player(db, player, found_game)
        if lookup.response:
            return lookup.response
        who = lookup.player

        rows = run(
            db,
            f"""
            WITH {entrants_cte('mine', 'pid')}
            SELECT sel.character_name AS character,
                   count(*) AS games,
                   count(*) FILTER (WHERE sg.winnerid = sel.entrantid) AS wins
            FROM mine m
            JOIN startgg_set_game_selections sel ON sel.entrantid = m.entrantid
            JOIN startgg_set_games sg ON sg.id = sel.set_game_id
            GROUP BY sel.character_name
            ORDER BY games DESC, character
            """,
            {"pid": who["id"], "game": found_game.id if found_game else None},
        )

        total = sum(r["games"] for r in rows)
        characters = [
            {
                "character": r["character"],
                "games": r["games"],
                "wins": r["wins"],
                "losses": r["games"] - r["wins"],
                "win_rate": rate(r["wins"], r["games"]),
            }
            for r in rows[:limit]
        ]
        scope = f" in {found_game.name}" if found_game else ""
        if total:
            top = characters[0]
            summary = (
                f"{who['gamertag']}{scope} has character data for {total} games; "
                f"most played is {top['character']} ({top['games']} games, {top['wins']} wins)."
            )
        else:
            summary = f"No character data has been reported for {who['gamertag']}{scope}."
        return {
            "status": "ok",
            "player": who,
            "game": found_game.name if found_game else None,
            "summary": summary,
            "games_with_character_data": total,
            "characters": characters,
        }

    @mcp.tool(annotations=READ_ONLY)
    def get_head_to_head(
        player_a: PlayerArg,
        player_b: PlayerArg,
        ctx: Context,
        game: GameArg = None,
        limit: Limit = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Two players' record against each other: sets and games won by each, and the
        most recent sets they played with event links. If either tag matches several
        players, returns candidates instead: show them to the user and ask which one
        they mean."""
        db = get_db(ctx)
        found_game = resolve_game(db, game)
        lookup_a = resolve_player(db, player_a, found_game)
        lookup_b = resolve_player(db, player_b, found_game)
        if lookup_a.response or lookup_b.response:
            statuses = [lk.response["status"] for lk in (lookup_a, lookup_b) if lk.response]
            return {
                "status": "ambiguous" if "ambiguous" in statuses else "not_found",
                "message": (
                    "Both players must be identified first. For each side marked below, "
                    "show the user the options and ask which player they mean, then call again "
                    "with the player ids. Do not pick one yourself."
                ),
                "player_a": lookup_a.response or {"status": "ok", "player": lookup_a.player},
                "player_b": lookup_b.response or {"status": "ok", "player": lookup_b.player},
            }
        a, b = lookup_a.player, lookup_b.player
        if a["id"] == b["id"]:
            raise ToolError("Both arguments refer to the same player.")

        rows = run(
            db,
            f"""
            WITH {entrants_cte('a', 'pa')}, {entrants_cte('b', 'pb')},
            pairs AS (
                SELECT s.*, s.playeronewins AS a_games, s.playertwowins AS b_games, s.entrantoneid AS a_entrant
                FROM a JOIN startgg_sets s ON s.entrantoneid = a.entrantid
                JOIN b ON b.entrantid = s.entranttwoid
                UNION ALL
                SELECT s.*, s.playertwowins, s.playeronewins, s.entranttwoid
                FROM a JOIN startgg_sets s ON s.entranttwoid = a.entrantid
                JOIN b ON b.entrantid = s.entrantoneid
            )
            SELECT (p.winnerid = p.a_entrant) AS a_won, p.a_games, p.b_games, p.hasdq,
                   to_char(coalesce(p.completedat, e.startdate), 'YYYY-MM-DD') AS date,
                   e.eventname, e.slug, t.tournamentname, g.name AS game
            FROM pairs p
            JOIN startgg_events e ON e.eventid = p.eventid
            JOIN startgg_tournaments t ON t.tournamentid = e.tournamentid
            JOIN startgg_videogames g ON g.id = e.videogameid
            ORDER BY coalesce(p.completedat, e.startdate) DESC, p.setid DESC
            """,
            {"pa": a["id"], "pb": b["id"], "game": found_game.id if found_game else None},
        )

        played = [r for r in rows if not r["hasdq"]]
        a_sets = sum(1 for r in played if r["a_won"])
        a_games = sum(max(r["a_games"] or 0, 0) for r in played)
        b_games = sum(max(r["b_games"] or 0, 0) for r in played)
        b_sets = len(played) - a_sets
        scope = f" in {found_game.name}" if found_game else ""
        if not played:
            summary = f"{a['gamertag']} and {b['gamertag']} have no recorded sets against each other{scope}."
        else:
            summary = (
                f"{a['gamertag']} vs {b['gamertag']}{scope}: {a_sets}-{b_sets} in sets, "
                f"{a_games}-{b_games} in games, over {len(played)} sets."
            )
        return {
            "status": "ok",
            "player_a": a,
            "player_b": b,
            "game": found_game.name if found_game else None,
            "summary": summary,
            "sets": len(played),
            "player_a_set_wins": a_sets,
            "player_b_set_wins": b_sets,
            "player_a_game_wins": a_games,
            "player_b_game_wins": b_games,
            "dq_sets_excluded": len(rows) - len(played),
            "recent_sets": [
                {
                    "date": r["date"],
                    "event": r["eventname"],
                    "tournament": r["tournamentname"],
                    "game": r["game"],
                    "winner": a["gamertag"] if r["a_won"] else b["gamertag"],
                    "score": f"{r['a_games']}-{r['b_games']}",
                    "disqualification": bool(r["hasdq"]),
                    "event_url": startgg_url(r["slug"]),
                }
                for r in rows[:limit]
            ],
        }
