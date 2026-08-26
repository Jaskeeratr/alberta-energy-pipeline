import pandas as pd
import pytest

from scripts import load


class FakeConnection:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.executed = []

    def execute(self, statement, parameters=None):
        if self.should_fail:
            raise RuntimeError("relation does not exist")
        self.executed.append((str(statement), parameters))
        return None


class FakeBegin:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeEngine:
    def __init__(self, should_fail=False):
        self.connection = FakeConnection(should_fail)

    def begin(self):
        return FakeBegin(self.connection)


def _sample_df(rows=1):
    return pd.DataFrame(
        [
            {
                "field_name": "LIGHT",
                "operator": "AER Summary",
                "production_date": "2024-01-01",
                "volume_m3": 1000 + i,
            }
            for i in range(rows)
        ]
    )


def _install_fake_engine(monkeypatch, engine):
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(load, "create_engine", lambda database_url: engine)


def test_load_oil_data_upserts_sample_data(monkeypatch):
    engine = FakeEngine()
    _install_fake_engine(monkeypatch, engine)

    load.load_oil_data(_sample_df())

    assert len(engine.connection.executed) == 1
    statement, parameters = engine.connection.executed[0]
    assert "INSERT INTO oil_production" in statement
    assert "ON CONFLICT (field_name, operator, production_date)" in statement
    assert "TRUNCATE" not in statement
    assert len(parameters) == 1
    assert parameters[0]["field_name"] == "LIGHT"


def test_load_splits_large_batches_into_chunks(monkeypatch):
    engine = FakeEngine()
    _install_fake_engine(monkeypatch, engine)
    monkeypatch.setattr(load, "UPSERT_CHUNK_SIZE", 2)

    load.load_gas_data(_sample_df(rows=5))

    batch_sizes = [len(parameters) for _, parameters in engine.connection.executed]
    assert batch_sizes == [2, 2, 1]
    assert all(
        "INSERT INTO gas_production" in statement
        for statement, _ in engine.connection.executed
    )


def test_load_skips_empty_dataframe_without_connecting(monkeypatch):
    def fail_create_engine(database_url):
        raise AssertionError("Should not connect when there is nothing to load")

    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(load, "create_engine", fail_create_engine)

    load.load_oil_data(pd.DataFrame())


def test_missing_expected_table_raises_clear_error(monkeypatch):
    _install_fake_engine(monkeypatch, FakeEngine(should_fail=True))

    with pytest.raises(RuntimeError, match="Failed to load data into oil_production"):
        load.load_oil_data(_sample_df())
