import pandas as pd
from pathlib import Path


def extract_oil_data(filepath: str) -> pd.DataFrame:
    """
    Load the 'Tables' sheet from the crude oil workbook exactly as-is.
    We use header=None because the workbook is a report layout, not a clean table.
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    suffix = path.suffix.lower()
    print(f"Extracting data from: {filepath}")

    if suffix in [".xlsx", ".xls"]:
        excel_file = pd.ExcelFile(path)
        print("Available sheets:", excel_file.sheet_names)

        df = pd.read_excel(path, sheet_name="Tables", header=None)
    else:
        raise ValueError("This version expects an Excel file (.xlsx or .xls).")

    print(f"Extracted {len(df):,} rows and {len(df.columns)} columns")
    return df