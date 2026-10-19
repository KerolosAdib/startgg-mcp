"""Driver tests: parameter handling in both drivers, and the Data API driver's
retries while Aurora resumes (against a stand-in for the AWS client)."""

import pytest

from startgg_mcp.db import DatabaseUnavailable, QueryTooSlow, create_db, data_api
from startgg_mcp.db.data_api import DataApiDatabase, to_parameter


def test_pg_named_parameters():
    db = create_db()
    try:
        [row] = db.query(
            "SELECT CAST(:n AS integer) + 1 AS n, 'a:b %' AS text, CAST('5' AS integer)::text AS cast",
            {"n": 41},
        )
    finally:
        db.close()
    assert row == {"n": 42, "text": "a:b %", "cast": "5"}


def test_data_api_parameters():
    assert to_parameter("a", None) == {"name": "a", "value": {"isNull": True}}
    assert to_parameter("a", True) == {"name": "a", "value": {"booleanValue": True}}
    assert to_parameter("a", 7) == {"name": "a", "value": {"longValue": 7}}
    assert to_parameter("a", 1.5) == {"name": "a", "value": {"doubleValue": 1.5}}
    assert to_parameter("a", "x") == {"name": "a", "value": {"stringValue": "x"}}
    with pytest.raises(TypeError):
        to_parameter("a", [1])


class FakeErrors:
    class DatabaseResumingException(Exception): ...
    class DatabaseUnavailableException(Exception): ...
    class StatementTimeoutException(Exception): ...
    class DatabaseErrorException(Exception): ...


class FakeClient:
    """Fails the first `resuming` calls the way a paused cluster does."""

    exceptions = FakeErrors

    def __init__(self, resuming: int, error: Exception | None = None):
        self.resuming = resuming
        self.error = error
        self.calls = []

    def execute_statement(self, **request):
        self.calls.append(request)
        if self.error:
            raise self.error
        if len(self.calls) <= self.resuming:
            raise FakeErrors.DatabaseResumingException("resuming")
        return {"formattedRecords": '[{"id": 1, "name": "x"}]'}

    def close(self):
        pass


@pytest.fixture
def aurora(monkeypatch):
    monkeypatch.setattr(data_api, "DB_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setattr(data_api, "DB_SECRET_ARN", "arn:secret")
    monkeypatch.setattr(data_api, "RESUME_RETRY_SECONDS", 0)
    monkeypatch.setattr(data_api.time, "sleep", lambda _: None)

    def make(client):
        monkeypatch.setattr(data_api.boto3, "client", lambda _: client)
        return DataApiDatabase()

    return make


def test_data_api_query(aurora):
    client = FakeClient(resuming=0)
    db = aurora(client)
    assert db.query("SELECT :id", {"id": 1}) == [{"id": 1, "name": "x"}]
    request = client.calls[0]
    assert request["formatRecordsAs"] == "JSON"
    assert request["parameters"] == [{"name": "id", "value": {"longValue": 1}}]


def test_data_api_waits_for_resume(aurora):
    client = FakeClient(resuming=3)
    assert aurora(client).query("SELECT 1") == [{"id": 1, "name": "x"}]
    assert len(client.calls) == 4


def test_data_api_gives_up(aurora, monkeypatch):
    monkeypatch.setattr(data_api, "RESUME_WAIT_SECONDS", 0)
    with pytest.raises(DatabaseUnavailable):
        aurora(FakeClient(resuming=100)).query("SELECT 1")


def test_data_api_statement_timeout(aurora):
    error = FakeErrors.DatabaseErrorException("ERROR: canceling statement due to statement timeout")
    with pytest.raises(QueryTooSlow):
        aurora(FakeClient(resuming=0, error=error)).query("SELECT 1")
