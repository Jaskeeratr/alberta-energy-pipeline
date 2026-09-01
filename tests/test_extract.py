import pandas as pd
import pytest

from scripts import extract
from scripts.extract import extract_gas_data, extract_oil_data


def _write_workbook(path, sheets):
    with pd.ExcelWriter(path) as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    return path


def test_extract_missing_file_raises_clear_error():
    with pytest.raises(FileNotFoundError, match="File not found"):
        extract_oil_data("data/raw/does_not_exist.xlsx")


def test_extract_rejects_non_excel_file(tmp_path):
    csv_path = tmp_path / "production.csv"
    csv_path.write_text("field_name,volume_m3\nLIGHT,1000\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expects an Excel file"):
        extract_oil_data(str(csv_path))


def test_extract_reads_tables_sheet_without_headers(tmp_path):
    raw = pd.DataFrame(
        [
            ["Table S4.1 Alberta crude oil production", None, None],
            [None, 2023, 2024],
            [" Light", 1.5, 2.0],
        ]
    )
    path = _write_workbook(tmp_path / "crude.xlsx", {"Tables": raw})

    result = extract_oil_data(str(path))

    # header=None keeps the report layout intact for the transform step.
    assert result.shape == (3, 3)
    assert result.iloc[0, 0] == "Table S4.1 Alberta crude oil production"
    assert result.iloc[1, 1] == 2023


def test_extract_gas_reads_same_sheet(tmp_path):
    raw = pd.DataFrame([["Table S5.1 Alberta natural gas production", None]])
    path = _write_workbook(tmp_path / "gas.xlsx", {"Tables": raw})

    result = extract_gas_data(str(path))

    assert result.iloc[0, 0] == "Table S5.1 Alberta natural gas production"


def test_extract_ignores_other_sheets(tmp_path):
    path = _write_workbook(
        tmp_path / "multi.xlsx",
        {
            "Notes": pd.DataFrame([["ignore me"]]),
            "Tables": pd.DataFrame([["Table S4.1"], [123]]),
        },
    )

    result = extract_oil_data(str(path))

    assert result.iloc[0, 0] == "Table S4.1"
    assert len(result) == 2


def test_extract_missing_tables_sheet_lists_available_sheets(tmp_path):
    path = _write_workbook(tmp_path / "wrong.xlsx", {"Summary": pd.DataFrame([[1]])})

    with pytest.raises(ValueError, match="Worksheet 'Tables' not found"):
        extract_oil_data(str(path))


def test_open_workbook_falls_back_when_fast_engine_missing(tmp_path, monkeypatch):
    path = _write_workbook(tmp_path / "fallback.xlsx", {"Tables": pd.DataFrame([["ok"]])})

    real_excel_file = pd.ExcelFile

    def fake_excel_file(target, engine=None):
        if engine == extract.PREFERRED_ENGINE:
            raise ImportError("python-calamine is not installed")
        return real_excel_file(target)

    monkeypatch.setattr(extract.pd, "ExcelFile", fake_excel_file)

    result = extract_oil_data(str(path))

    assert result.iloc[0, 0] == "ok"
