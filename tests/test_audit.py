import json

import pandas as pd
import pytest

from scripts import load
from scripts.load import (
    create_pipeline_run,
    finish_pipeline_run,
    get_database_url,
    load_data_quality_issues,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeConnection:
    def __init__(self, scalar_value=42):
        self.scalar_value = scalar_value
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((str(statement), parameters))
        return FakeResult(self.scalar_value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeEngine:
    def __init__(self, scalar_value=42):
        self.connection = FakeConnection(scalar_value)

    def begin(self):
        return self.connection


@pytest.fixture
def fake_engine(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(load, "create_engine", lambda url: engine)
    return engine


def test_database_url_built_from_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "etl_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss word")
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "energy")

    url = get_database_url()

    # Credentials must be URL-encoded so special characters cannot break the DSN.
    assert url == "postgresql://etl_user:p%40ss+word@db.internal:6543/energy"


def test_database_url_prefers_explicit_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://override/db")
    monkeypatch.setenv("POSTGRES_PASSWORD", "ignored")

    assert get_database_url() == "postgresql://override/db"


def test_missing_password_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Set POSTGRES_PASSWORD or DATABASE_URL"):
        get_database_url()


def test_create_pipeline_run_returns_run_id(fake_engine):
    run_id = create_pipeline_run("crude_oil")

    assert run_id == 42
    statement, parameters = fake_engine.connection.calls[0]
    assert "INSERT INTO pipeline_runs" in statement
    assert parameters == {"source_name": "crude_oil"}


def test_finish_pipeline_run_records_success_metrics(fake_engine):
    finish_pipeline_run(
        run_id=7,
        status="success",
        rows_extracted=100,
        rows_loaded=95,
        rows_rejected=5,
        error_rate=0.05,
    )

    statement, parameters = fake_engine.connection.calls[0]
    assert "UPDATE pipeline_runs" in statement
    assert parameters["run_id"] == 7
    assert parameters["status"] == "success"
    assert parameters["rows_loaded"] == 95
    assert parameters["error_rate"] == 0.05
    assert parameters["error_message"] is None


def test_finish_pipeline_run_records_failure_message(fake_engine):
    finish_pipeline_run(run_id=8, status="failed", error_message="boom")

    _, parameters = fake_engine.connection.calls[0]
    assert parameters["status"] == "failed"
    assert parameters["error_message"] == "boom"


def test_load_data_quality_issues_expands_each_error_type(fake_engine):
    rejected_df = pd.DataFrame(
        [
            {
                "field_name": "",
                "operator": "AER Summary",
                "production_date": "2024-01-01",
                "volume_m3": -1,
                "validation_errors": "missing_field_name;negative_volume",
            }
        ]
    )

    load_data_quality_issues(run_id=3, source_name="crude_oil", rejected_df=rejected_df)

    _, parameters = fake_engine.connection.calls[0]
    # One row per issue type so each failure is queryable on its own.
    assert [row["issue_type"] for row in parameters] == [
        "missing_field_name",
        "negative_volume",
    ]
    assert all(row["pipeline_run_id"] == 3 for row in parameters)
    assert json.loads(parameters[0]["issue_detail"])["operator"] == "AER Summary"


def test_load_data_quality_issues_skips_when_nothing_rejected(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    def fail_create_engine(url):
        raise AssertionError("Should not connect when there are no issues")

    monkeypatch.setattr(load, "create_engine", fail_create_engine)

    load_data_quality_issues(1, "crude_oil", pd.DataFrame())
