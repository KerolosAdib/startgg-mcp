"""Test setup: a fresh Postgres database loaded with schema.sql and seed.sql.

Uses the PG* environment variables for the server to connect to (for example
the Podman container from the README), and creates a separate database named
startgg_mcp_test there so your own data is never touched.
"""

import os
from pathlib import Path
from typing import Any

import psycopg
import pytest
from mcp import Client

from startgg_mcp.config import DB_DRIVER
from startgg_mcp.server import mcp

TEST_DB = "startgg_mcp_test"
HERE = Path(__file__).parent


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    assert DB_DRIVER == "pg", "Tests run against local Postgres: set DB_DRIVER=pg"
    # The server's connection pool reads PGDATABASE when it connects
    os.environ["PGDATABASE"] = TEST_DB
    with psycopg.connect(dbname="postgres", autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    with psycopg.connect(dbname=TEST_DB, autocommit=True) as conn:
        conn.execute((HERE / "schema.sql").read_text())
        conn.execute((HERE / "seed.sql").read_text())


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c


@pytest.fixture
def call(client):
    """Call a tool and return its structured result, or the error text."""

    async def _call(name: str, **args: Any) -> dict[str, Any]:
        result = await client.call_tool(name, args)
        if result.is_error:
            return {"error": " ".join(c.text for c in result.content)}
        return result.structured_content

    return _call
