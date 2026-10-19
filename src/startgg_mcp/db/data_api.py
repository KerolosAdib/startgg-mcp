import json
import time
from typing import Any

import boto3

from ..config import DB_CLUSTER_ARN, DB_NAME, DB_SECRET_ARN, RESUME_WAIT_SECONDS
from .errors import DatabaseUnavailable, QueryTooSlow

RESUME_RETRY_SECONDS = 5


def to_parameter(name: str, value: Any) -> dict[str, Any]:
    """A Python value as a typed RDS Data API parameter."""
    if value is None:
        field: dict[str, Any] = {"isNull": True}
    elif isinstance(value, bool):
        field = {"booleanValue": value}
    elif isinstance(value, int):
        field = {"longValue": value}
    elif isinstance(value, float):
        field = {"doubleValue": value}
    elif isinstance(value, str):
        field = {"stringValue": value}
    else:
        raise TypeError(f"Unsupported parameter type for {name}: {type(value).__name__}")
    return {"name": name, "value": field}


class DataApiDatabase:
    """Aurora through the RDS Data API. Uses the cluster ARN, secret ARN and database
    name from config, and AWS credentials from the environment (SSO locally, the
    Lambda's role in AWS)."""

    def __init__(self) -> None:
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            raise ValueError("DB_CLUSTER_ARN and DB_SECRET_ARN must be set for the data-api driver")
        self.client = boto3.client("rds-data")

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        request = {
            "resourceArn": DB_CLUSTER_ARN,
            "secretArn": DB_SECRET_ARN,
            "database": DB_NAME,
            "sql": sql,
            "parameters": [to_parameter(k, v) for k, v in (params or {}).items()],
            "formatRecordsAs": "JSON",
        }
        errors = self.client.exceptions
        deadline = time.monotonic() + RESUME_WAIT_SECONDS

        # A paused Aurora cluster rejects requests until it has resumed
        while True:
            try:
                response = self.client.execute_statement(**request)
                return json.loads(response.get("formattedRecords") or "[]")
            except (errors.DatabaseResumingException, errors.DatabaseUnavailableException) as err:
                if time.monotonic() + RESUME_RETRY_SECONDS > deadline:
                    raise DatabaseUnavailable(str(err)) from err
                time.sleep(RESUME_RETRY_SECONDS)
            except errors.StatementTimeoutException as err:
                raise QueryTooSlow(str(err)) from err
            except errors.DatabaseErrorException as err:
                if "statement timeout" in str(err):
                    raise QueryTooSlow(str(err)) from err
                raise

    def close(self) -> None:
        self.client.close()
