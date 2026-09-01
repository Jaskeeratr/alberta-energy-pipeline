import pandas as pd
from pathlib import Path


EXCEL_SUFFIXES = (".xlsx", ".xls")
SHEET_NAME = "Tables"

# calamine is a Rust-backed reader roughly three orders of magnitude faster
# than openpyxl on these workbooks. It is optional: if it is not installed we
# fall back to pandas' default engine, which produces identical frames.
PREFERRED_ENGINE = "calamine"


def _open_workbook(path: Path) -> pd.ExcelFile:
    """Open the workbook once, preferring the fast engine when available."""
    try:
        return pd.ExcelFile(path, engine=PREFERRED_ENGINE)
    except ImportError:
        return pd.ExcelFile(path)


def _extract_tables_sheet(filepath: str) -> pd.DataFrame:
    """
    Load the 'Tables' sheet from an AER workbook exactly as-is.

    We use header=None because the workbook is a report layout, not a clean
    table; the transform step locates the target table within the raw grid.
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if path.suffix.lower() not in EXCEL_SUFFIXES:
        raise ValueError("This version expects an Excel file (.xlsx or .xls).")

    print(f"Extracting data from: {filepath}")

    # Reuse the open handle for both the sheet listing and the read so the
    # workbook is parsed once rather than twice.
    workbook = _open_workbook(path)
    print("Available sheets:", workbook.sheet_names)

    if SHEET_NAME not in workbook.sheet_names:
        raise ValueError(
            f"Worksheet '{SHEET_NAME}' not found in {filepath}. "
            f"Available sheets: {workbook.sheet_names}"
        )

    df = pd.read_excel(workbook, sheet_name=SHEET_NAME, header=None)

    print(f"Extracted {len(df):,} rows and {len(df.columns)} columns")
    return df


def extract_oil_data(filepath: str) -> pd.DataFrame:
    """Load the 'Tables' sheet from the crude oil workbook."""
    return _extract_tables_sheet(filepath)


def extract_gas_data(filepath: str) -> pd.DataFrame:
    """Load the 'Tables' sheet from the natural gas workbook."""
    return _extract_tables_sheet(filepath)
