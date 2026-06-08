import pandas as pd

from scripts.transform import transform_gas_data, transform_oil_data


def test_transform_oil_data_creates_expected_columns():
    raw_df = pd.DataFrame(
        [
            [None, None, None],
            ["Table S4.1 Alberta crude oil production", None, None],
            [None, 2023, 2024],
            ["Crude oil production (103 m3/d)", None, None],
            [" Light", 1.5, 2.0],
            ["number of wells placed on production", None, None],
        ]
    )

    result = transform_oil_data(raw_df)

    assert list(result.columns) == [
        "field_name",
        "operator",
        "production_date",
        "volume_m3",
    ]
    assert len(result) == 2
    assert result.iloc[0]["field_name"] == "LIGHT"
    assert result.iloc[0]["volume_m3"] == 1500


def test_transform_gas_data_creates_expected_columns():
    raw_df = pd.DataFrame(
        [
            [None, None, None],
            ["Table S5.1 Alberta natural gas production", None, None],
            [None, 2023, 2024],
            ["Marketable production (106 m3/d)", None, None],
            [" Gasa", 1.0, 2.0],
            ["Number of new wells placed on production", None, None],
        ]
    )

    result = transform_gas_data(raw_df)

    assert len(result) == 2
    assert result.iloc[0]["field_name"] == "GAS"
    assert result.iloc[0]["volume_m3"] == 1_000_000
