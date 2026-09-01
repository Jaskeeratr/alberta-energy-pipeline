import pandas as pd

from scripts import benchmark_extract
from scripts.benchmark_extract import (
    benchmark_source,
    legacy_extract,
    main,
    time_extraction,
)


def _write_workbook(path):
    frame = pd.DataFrame(
        [
            ["Table S4.1 Alberta crude oil production", None, None],
            [None, 2023, 2024],
            [" Light", 1.5, 2.0],
        ]
    )
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="Tables", index=False, header=False)
    return str(path)


def test_legacy_extract_still_reads_the_tables_sheet(tmp_path):
    path = _write_workbook(tmp_path / "crude.xlsx")

    result = legacy_extract(path)

    assert result.shape == (3, 3)
    assert result.iloc[0, 0] == "Table S4.1 Alberta crude oil production"


def test_time_extraction_reports_min_and_mean():
    calls = []

    best, mean = time_extraction(lambda path: calls.append(path), "any.xlsx", runs=3)

    assert len(calls) == 3
    assert best <= mean


def test_benchmark_source_skips_missing_file(capsys):
    assert benchmark_source("crude_oil", "data/raw/missing.xlsx", runs=1) is None
    assert "Skipping crude_oil" in capsys.readouterr().out


def test_benchmark_source_compares_both_implementations(tmp_path):
    path = _write_workbook(tmp_path / "crude.xlsx")

    result = benchmark_source("crude_oil", path, runs=1)

    assert result["source_name"] == "crude_oil"
    assert result["identical_output"] is True
    assert result["speedup"] > 0
    assert result["current_mean"] > 0


def test_main_prints_a_comparison_table(tmp_path, monkeypatch, capsys):
    path = _write_workbook(tmp_path / "crude.xlsx")
    monkeypatch.setattr(benchmark_extract, "DEFAULT_SOURCES", {"crude_oil": path})
    monkeypatch.setattr("sys.argv", ["benchmark_extract.py", "--runs", "1"])

    main()

    output = capsys.readouterr().out
    assert "Extraction benchmark" in output
    assert "crude_oil" in output
    assert "speedup" in output
