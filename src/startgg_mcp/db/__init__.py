from typing import Any, Protocol

from ..config import DB_DRIVER
from .data_api import DataApiDatabase
from .errors import DatabaseUnavailable, QueryTooSlow
from .pg import PgDatabase

__all__ = ["Database", "DatabaseUnavailable", "QueryTooSlow", "create_db"]


class Database(Protocol):
    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


def create_db() -> Database:
    if DB_DRIVER == "pg":
        return PgDatabase()
    if DB_DRIVER == "data-api":
        return DataApiDatabase()
    raise ValueError(f"Unknown DB_DRIVER: {DB_DRIVER!r}")