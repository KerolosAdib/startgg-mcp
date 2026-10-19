import re
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from ..config import STATEMENT_TIMEOUT_SECONDS
from .errors import DatabaseUnavailable, QueryTooSlow

# Matches a quoted string (left as is) or a :name parameter (not a ::cast)
NAMED_PARAM = re.compile(r"'(?:[^']|'')*'|(?<!:):([A-Za-z_]\w*)")

class PgDatabase:
    """Local Postgres through a psycopg connection pool. Settings come from PG* env vars."""

    def __init__(self) -> None:
        self.pool = ConnectionPool(
            conninfo="",
            min_size=1,
            max_size=5,
            timeout=10,
            open=True,
            kwargs={
                "row_factory": dict_row,
                "options": f"-c statement_timeout={STATEMENT_TIMEOUT_SECONDS * 1000}",
            },
        )

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        # psycopg uses %(name)s, so escape literal % first, then convert :name
        sql = NAMED_PARAM.sub(
            lambda m: f"%({m.group(1)})s" if m.group(1) else m.group(0),
            sql.replace("%", "%%"),
        )
        try:
            with self.pool.connection() as conn:
                return conn.execute(sql, params or {}).fetchall()
        except psycopg.errors.QueryCanceled as err:
            raise QueryTooSlow(str(err)) from err
        except (PoolTimeout, psycopg.OperationalError) as err:
            raise DatabaseUnavailable(str(err)) from err

    def close(self) -> None:
        self.pool.close()
