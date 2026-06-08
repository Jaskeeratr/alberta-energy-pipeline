import pandas as pd

from scripts.validate import validate_production_data


def _valid_row(**overrides):
    row = {
        "field_name": "LIGHT",
        "operator": "AER Summary",
        "production_date": "2024-01-01",
        "volume_m3": 1000,
    }
    row.update(overrides)
    return row


def test_validation_catches_missing_values():
    df = pd.DataFrame([_valid_row(field_name="")])

    valid_df, rejected_df, summary = validate_production_data(df, "crude_oil")

    assert valid_df.empty
    assert len(rejected_df) == 1
    assert summary["validation_errors_by_type"]["missing_field_name"] == 1


def test_validation_catches_negative_production_values():
    df = pd.DataFrame([_valid_row(volume_m3=-1)])

    valid_df, rejected_df, summary = validate_production_data(df, "crude_oil")

    assert valid_df.empty
    assert len(rejected_df) == 1
    assert summary["validation_errors_by_type"]["negative_volume"] == 1


def test_validation_catches_duplicates():
    df = pd.DataFrame([_valid_row(), _valid_row()])

    valid_df, rejected_df, summary = validate_production_data(df, "crude_oil")

    assert valid_df.empty
    assert len(rejected_df) == 2
    assert summary["validation_errors_by_type"]["duplicate_record"] == 2


def test_validation_catches_invalid_dates():
    df = pd.DataFrame([_valid_row(production_date="not-a-date")])

    valid_df, rejected_df, summary = validate_production_data(df, "crude_oil")

    assert valid_df.empty
    assert len(rejected_df) == 1
    assert summary["validation_errors_by_type"]["invalid_production_date"] == 1
