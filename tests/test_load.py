import pandas as pd
import pytest

from scripts import load


class FakeConnection:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def execute(self, statement):
        if self.should_fail:
            raise RuntimeError("relation does not exist")
        return None


class FakeBegin:
    def __init__(self, should_fail=False):
        self.connection = FakeConnection(should_fail)

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeEngine:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def begin(self):
        return FakeBegin(self.should_fail)


def test_load_oil_data_inserts_sample_data(monkeypatch):
    calls = {}

    def fake_create_engine(database_url):
        calls["database_url"] = database_url
        return FakeEngine()

    def fake_to_sql(self, **kwargs):
        calls["table_name"] = kwargs["name"]
        calls["row_count"] = len(self)

    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(load, "create_engine", fake_create_engine)
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    sample_df = pd.DataFrame(
        [
            {
                "field_name": "LIGHT",
                "operator": "AER Summary",
                "production_date": "2024-01-01",
                "volume_m3": 1000,
            }
        ]
    )

    load.load_oil_data(sample_df)

    assert calls["table_name"] == "oil_production"
    assert calls["row_count"] == 1
    assert "postgresql://" in calls["database_url"]


def test_missing_expected_table_raises_clear_error(monkeypatch):
    def fake_create_engine(database_url):
        return FakeEngine(should_fail=True)

    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(load, "create_engine", fake_create_engine)

    with pytest.raises(RuntimeError, match="Failed to load data into oil_production"):
        load.load_oil_data(pd.DataFrame())
