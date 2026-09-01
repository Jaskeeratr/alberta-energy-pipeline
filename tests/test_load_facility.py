import pandas as pd
import pytest

from scripts import load
from scripts.load import FACILITY_COLUMNS, load_facility_production


class FakeCursor:
    def __init__(self, recorder):
        self.recorder = recorder

    def execute(self, statement):
        self.recorder["statements"].append(" ".join(statement.split()))

    def copy_expert(self, statement, buffer):
        self.recorder["copy_statement"] = " ".join(statement.split())
        self.recorder["copied"] = buffer.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeRawConnection:
    def __init__(self, recorder):
        self.recorder = recorder

    def cursor(self):
        return FakeCursor(self.recorder)


class FakeSAConnection:
    def __init__(self, recorder):
        self.connection = FakeRawConnection(recorder)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeEngine:
    def __init__(self, recorder):
        self.recorder = recorder

    def begin(self):
        return FakeSAConnection(self.recorder)


def _facility_df(rows=1, **overrides):
    base = {
        "production_month": "2026-03-01",
        "operator_ba_id": "0007",
        "operator_name": "IMPERIAL OIL RESOURCES LIMITED",
        "facility_id": "ABBT0051211",
        "facility_type": "BT",
        "facility_subtype_desc": "IN-SITU OIL SANDS",
        "facility_name": "MASKWA BATTERY",
        "facility_location": "10-12-065-04W4",
        "activity_id": "PROD",
        "product_id": "GAS",
        "from_to_id": "",
        "volume": 1234.5,
        "energy": None,
        "hours": 720,
        "volume_masked": False,
    }
    base.update(overrides)
    return pd.DataFrame([{**base, "facility_id": f"FAC{i}"} for i in range(rows)])


@pytest.fixture
def recorder(monkeypatch):
    rec = {"statements": [], "copy_statement": None, "copied": None}
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(load, "create_engine", lambda url: FakeEngine(rec))
    return rec


def test_bulk_load_stages_then_merges(recorder):
    rows_loaded = load_facility_production(_facility_df(rows=3))

    assert rows_loaded == 3
    statements = recorder["statements"]
    # Stage into a temp table, then merge in one set-based statement.
    assert any("CREATE TEMP TABLE tmp_facility_production" in s for s in statements)
    merge = next(s for s in statements if s.startswith("INSERT INTO facility_production"))
    assert "SELECT" in merge and "tmp_facility_production" in merge
    assert "ON CONFLICT (production_month, facility_id, activity_id, product_id, from_to_id)" in merge
    assert "DO UPDATE SET" in merge


def test_bulk_load_uses_copy_with_explicit_columns(recorder):
    load_facility_production(_facility_df())

    copy_statement = recorder["copy_statement"]
    assert copy_statement.startswith("COPY tmp_facility_production")
    assert "FROM STDIN WITH (FORMAT csv" in copy_statement
    for column in FACILITY_COLUMNS:
        assert column in copy_statement


def test_bulk_load_writes_nulls_as_copy_sentinel(recorder):
    load_facility_production(_facility_df(energy=None))

    # A bare empty field would be read as an empty string, not NULL.
    assert r"\N" in recorder["copied"]


def test_bulk_load_orders_columns_to_match_copy_list(recorder):
    scrambled = _facility_df()[list(reversed(FACILITY_COLUMNS))]

    load_facility_production(scrambled)

    first_row = recorder["copied"].splitlines()[0].split(",")
    # production_month is first in FACILITY_COLUMNS regardless of input order.
    assert first_row[0] == "2026-03-01"


def test_bulk_load_skips_empty_frame(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(
        load,
        "create_engine",
        lambda url: (_ for _ in ()).throw(AssertionError("should not connect")),
    )

    assert load_facility_production(pd.DataFrame()) == 0


def test_bulk_load_wraps_failures(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    def boom(url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(load, "create_engine", boom)

    with pytest.raises(RuntimeError, match="Failed to load data into facility_production"):
        load_facility_production(_facility_df())
