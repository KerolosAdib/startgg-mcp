"""Helpers shared by the tools and the player and game lookups."""

from typing import Annotated, Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import MAX_LIMIT
from .db import Database, DatabaseUnavailable, QueryTooSlow

# Every tool only reads data the scraper already stored
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

# Separator for lists aggregated in SQL with chr(31); never appears in names
LIST_SEP = "\x1f"

Limit = Annotated[int, Field(ge=1, le=MAX_LIMIT, description=f"Maximum rows to return (1-{MAX_LIMIT}).")]
GameArg = Annotated[
    str | None,
    Field(description="Game name or ID, e.g. 'Street Fighter 6'. Call list_games for exact names."),
]
PlayerArg = Annotated[
    str,
    Field(description="Gamertag, or a numeric player ID from an earlier result."),
]


def get_db(ctx: Context) -> Database:
    """The database client created by the server's lifespan."""
    return ctx.request_context.lifespan_context.db


def run(db: Database, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a query, turning database failures into errors the model can read."""
    try:
        return db.query(sql, params)
    except DatabaseUnavailable as err:
        raise ToolError(
            "The database is unavailable or still waking up. Try again in a minute."
        ) from err
    except QueryTooSlow as err:
        raise ToolError(
            "That query took too long. Narrow it down, for example with a game or a smaller limit."
        ) from err


def id_list(ids: list[int]) -> str:
    """IDs as a comma-separated string, for `string_to_array(:ids, ',')` in SQL
    (the RDS Data API does not accept array parameters)."""
    return ",".join(str(int(i)) for i in ids)


def split_list(value: str | None) -> list[str]:
    """Split a list aggregated in SQL with LIST_SEP."""
    return [v for v in (value or "").split(LIST_SEP) if v]


def rate(wins: int, total: int) -> float | None:
    """Win rate rounded to 3 decimals, or None with no sample."""
    return round(wins / total, 3) if total else None


def like_pattern(text: str) -> str:
    """Escape LIKE wildcards so the text matches literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
