from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd


REQUIRED_COLUMNS = ["field_name", "operator", "production_date", "volume_m3"]


def _add_error(errors: Dict[int, List[str]], row_index: int, issue_type: str) -> None:
    errors.setdefault(row_index, []).append(issue_type)


def validate_production_data(
    df: pd.DataFrame,
    source_name: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Validate normalized production records before loading them into PostgreSQL.

    Returns valid rows, rejected rows, and a summary dictionary.
    """
    rows_extracted = len(df)
    errors: Dict[int, List[str]] = {}

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        rejected_df = df.copy()
        rejected_df["source_name"] = source_name
        rejected_df["validation_errors"] = "missing_required_columns"

        summary = {
            "source_name": source_name,
            "rows_extracted": rows_extracted,
            "rows_valid": 0,
            "rows_rejected": rows_extracted,
            "error_rate": 1.0 if rows_extracted else 0.0,
            "validation_errors_by_type": {
                "missing_required_columns": len(missing_columns)
            },
            "missing_columns": missing_columns,
        }
        return df.iloc[0:0].copy(), rejected_df, summary

    working_df = df.copy()

    for col in ["field_name", "operator"]:
        missing_mask = working_df[col].isna() | (working_df[col].astype(str).str.strip() == "")
        for row_index in working_df[missing_mask].index:
            _add_error(errors, row_index, f"missing_{col}")

    numeric_values = pd.to_numeric(working_df["volume_m3"], errors="coerce")
    invalid_numeric_mask = numeric_values.isna()
    for row_index in working_df[invalid_numeric_mask].index:
        _add_error(errors, row_index, "invalid_volume")

    negative_mask = numeric_values.notna() & (numeric_values < 0)
    for row_index in working_df[negative_mask].index:
        _add_error(errors, row_index, "negative_volume")

    date_values = pd.to_datetime(working_df["production_date"], errors="coerce")
    invalid_date_mask = date_values.isna()
    for row_index in working_df[invalid_date_mask].index:
        _add_error(errors, row_index, "invalid_production_date")

    valid_year_mask = date_values.dt.year.between(1900, 2100)
    invalid_year_mask = date_values.notna() & ~valid_year_mask
    for row_index in working_df[invalid_year_mask].index:
        _add_error(errors, row_index, "invalid_production_year")

    duplicate_mask = working_df.duplicated(
        subset=["field_name", "operator", "production_date"],
        keep=False,
    )
    for row_index in working_df[duplicate_mask].index:
        _add_error(errors, row_index, "duplicate_record")

    rejected_indexes = sorted(errors.keys())
    valid_df = working_df.drop(index=rejected_indexes).copy()
    rejected_df = working_df.loc[rejected_indexes].copy()

    if not valid_df.empty:
        valid_df["volume_m3"] = pd.to_numeric(valid_df["volume_m3"], errors="coerce")
        valid_df["production_date"] = pd.to_datetime(
            valid_df["production_date"],
            errors="coerce",
        ).dt.date

    if not rejected_df.empty:
        rejected_df["source_name"] = source_name
        rejected_df["validation_errors"] = [
            ";".join(errors[row_index]) for row_index in rejected_indexes
        ]

    errors_by_type: Dict[str, int] = {}
    for row_errors in errors.values():
        for issue_type in row_errors:
            errors_by_type[issue_type] = errors_by_type.get(issue_type, 0) + 1

    rows_rejected = len(rejected_df)
    summary = {
        "source_name": source_name,
        "rows_extracted": rows_extracted,
        "rows_valid": len(valid_df),
        "rows_rejected": rows_rejected,
        "error_rate": round(rows_rejected / rows_extracted, 4) if rows_extracted else 0.0,
        "validation_errors_by_type": errors_by_type,
    }

    return valid_df, rejected_df, summary
