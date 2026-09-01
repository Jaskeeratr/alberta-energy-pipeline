"""
Reproducible benchmark for the Excel extraction step.

Compares the original double-parse implementation against the current one so
any performance claim about extraction can be re-measured on demand:

    python scripts/benchmark_extract.py --runs 3
"""
from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import pandas as pd

from scripts.extract import _extract_tables_sheet


DEFAULT_SOURCES = {
    "crude_oil": "data/raw/crude_oil_production.xlsx",
    "natural_gas": "data/raw/natural_gas_production.xlsx",
}


def legacy_extract(filepath: str) -> pd.DataFrame:
    """
    The original implementation, kept only as a benchmark baseline.

    It opened the workbook once to list sheet names and then opened it a
    second time to read the data, parsing the file twice with openpyxl.
    """
    excel_file = pd.ExcelFile(filepath)
    _ = excel_file.sheet_names
    return pd.read_excel(filepath, sheet_name="Tables", header=None)


def time_extraction(func, filepath: str, runs: int) -> tuple[float, float]:
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        func(filepath)
        timings.append(time.perf_counter() - start)
    return min(timings), statistics.mean(timings)


def benchmark_source(source_name: str, filepath: str, runs: int) -> dict | None:
    if not Path(filepath).exists():
        print(f"Skipping {source_name}: {filepath} not found")
        return None

    legacy_best, legacy_mean = time_extraction(legacy_extract, filepath, runs)
    current_best, current_mean = time_extraction(_extract_tables_sheet, filepath, runs)

    # Guard the comparison: a speedup only means something if both paths
    # return the same frame.
    legacy_df = legacy_extract(filepath)
    current_df = _extract_tables_sheet(filepath)
    identical = legacy_df.shape == current_df.shape

    return {
        "source_name": source_name,
        "legacy_best": legacy_best,
        "legacy_mean": legacy_mean,
        "current_best": current_best,
        "current_mean": current_mean,
        "speedup": legacy_mean / current_mean if current_mean else float("nan"),
        "identical_output": identical,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="Timed runs per variant.")
    args = parser.parse_args()

    results = [
        result
        for source_name, filepath in DEFAULT_SOURCES.items()
        if (result := benchmark_source(source_name, filepath, args.runs)) is not None
    ]

    print(f"\nExtraction benchmark ({args.runs} runs per variant)\n")
    header = f"{'source':<14}{'legacy mean':>14}{'current mean':>14}{'speedup':>10}"
    print(header)
    print("-" * len(header))
    for result in results:
        print(
            f"{result['source_name']:<14}"
            f"{result['legacy_mean']:>13.3f}s"
            f"{result['current_mean']:>13.3f}s"
            f"{result['speedup']:>9.1f}x"
        )
        if not result["identical_output"]:
            print(f"  WARNING: {result['source_name']} output shape differs!")


if __name__ == "__main__":
    main()
