from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer

from .config import SMALL_SAMPLE_GAMES, SMALL_SAMPLE_SETS
from .db import Database, create_db
from .tools import characters, games, players, tournaments

INSTRUCTIONS = f"""\
This server answers questions about competitive fighting game results using \
tournament data scraped from start.gg. It is read-only and is not live: data is \
refreshed about once a day, so recent events may be missing.

Coverage: only the games returned by list_games. If you are unsure which games are \
covered or what a game's exact name is, call list_games first. If a question is \
about a game that isn't covered, say so; don't answer from general knowledge as if \
it came from this data.

Players:
- Gamertags are not unique. If a tool returns status "ambiguous", do not pick a \
candidate yourself. Show the user the candidates with their games, activity and \
profile links, ask which one they mean, then call the tool again with that \
player's id.
- When the user names a game, pass it as `game`; it often narrows a common tag to \
one person.
- Gamertags can change over time; results are listed under the player's current tag.

Reporting results:
- Include the start.gg links the tools return for players, events and tournaments.
- State sample sizes (sets or games) next to any record or win rate, and point out \
when a sample is small (under ~{SMALL_SAMPLE_SETS} sets or ~{SMALL_SAMPLE_GAMES} games).
- Character data only covers games where the organizer reported characters, so \
character stats describe that subset, not every match.
- Only report numbers the tools returned. If the data can't answer the question, \
say what is missing instead of estimating.
"""

@dataclass
class AppState:
    db: Database

@asynccontextmanager
async def lifespan(server):
    db = create_db()
    try:
        yield AppState(db=db)
    finally:
        db.close()

mcp = MCPServer("startgg", instructions=INSTRUCTIONS, lifespan=lifespan)

for module in (games, players, characters, tournaments):
    module.register(mcp)
