import io
import zipfile

import pandas as pd
import pytest

from scripts import petrinex
from scripts.petrinex import (
    NATURAL_KEY,
    extract_petrinex_data,
    get_month_url,
    transform_petrinex_data,
    validate_month,
)


RAW_COLUMNS = [
    "ProductionMonth", "OperatorBAID", "OperatorName", "ReportingFacilityID",
    "ReportingFacilityProvinceState", "ReportingFacilityType",
    "ReportingFacilityIdentifier", "ReportingFacilityName",
    "ReportingFacilitySubType", "ReportingFacilitySubTypeDesc",
    "ReportingFacilityLocation", "FacilityLegalSubdivision", "FacilitySection",
    "FacilityTownship", "FacilityRange", "FacilityMeridian", "SubmissionDate",
    "ActivityID", "ProductID", "FromToID", "FromToIDProvinceState",
    "FromToIDType", "FromToIDIdentifier", "Volume", "Energy", "Hours",
    "CCICode", "ProrationProduct", "ProrationFactor", "Heat",
]


def _raw_row(**overrides):
    row = {col: None for col in RAW_COLUMNS}
    row.update(
        {
            "ProductionMonth": "2026-03",
            "OperatorBAID": "0007",
            "OperatorName": "IMPERIAL OIL RESOURCES LIMITED",
            "ReportingFacilityID": "ABBT0051211",
            "ReportingFacilityType": "BT",
            "ReportingFacilitySubTypeDesc": "IN-SITU OIL SANDS",
            "ReportingFacilityName": "IMPERIAL MASKWA BATTERY 10-12",
            "ReportingFacilityLocation": "10-12-065-04W4",
            "ActivityID": "PROD",
            "ProductID": "GAS",
            "FromToID": "",
            "Volume": "1234.5",
            "Hours": "720",
        }
    )
    row.update(overrides)
    return row


def _raw_frame(rows):
    return pd.DataFrame(rows, columns=RAW_COLUMNS).astype(object)


def _write_nested_archive(path, frame):
    """Build the zip-inside-a-zip layout Petrinex actually publishes."""
    csv_bytes = frame.to_csv(index=False).encode("utf-8")

    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, "w") as inner:
        inner.writestr("Vol_2026-03-AB.CSV", csv_bytes)

    with zipfile.ZipFile(path, "w") as outer:
        outer.writestr("Vol_2026-03-AB.csv.zip", inner_buffer.getvalue())
    return str(path)


def test_validate_month_accepts_valid_month():
    validate_month("2026-03")


@pytest.mark.parametrize("bad", ["2026", "2026-3", "202603", "2026-13", "abcd-ef"])
def test_validate_month_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        validate_month(bad)


def test_get_month_url_builds_expected_url(monkeypatch):
    monkeypatch.delenv("PETRINEX_URL_TEMPLATE", raising=False)
    assert get_month_url("2026-03").endswith("/AB/Vol/2026-03/CSV")


def test_get_month_url_honors_override(monkeypatch):
    monkeypatch.setenv("PETRINEX_URL_TEMPLATE", "https://example.com/{month}.zip")
    assert get_month_url("2026-03") == "https://example.com/2026-03.zip"


def test_extract_missing_archive_raises():
    with pytest.raises(FileNotFoundError, match="File not found"):
        extract_petrinex_data("data/raw/petrinex/missing.zip")


def test_extract_reads_nested_archive(tmp_path):
    path = _write_nested_archive(tmp_path / "vol.zip", _raw_frame([_raw_row()]))

    result = extract_petrinex_data(path)

    assert len(result) == 1
    assert result.iloc[0]["ReportingFacilityID"] == "ABBT0051211"


def test_extract_reads_flat_archive(tmp_path):
    path = tmp_path / "flat.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Vol.csv", _raw_frame([_raw_row()]).to_csv(index=False))

    assert len(extract_petrinex_data(str(path))) == 1


def test_transform_normalizes_columns_and_month():
    result = transform_petrinex_data(_raw_frame([_raw_row()]))

    assert result.iloc[0]["facility_id"] == "ABBT0051211"
    assert str(result.iloc[0]["production_month"]) == "2026-03-01"
    assert result.iloc[0]["volume"] == 1234.5
    assert result.iloc[0]["volume_masked"] is False or not result.iloc[0]["volume_masked"]


def test_transform_drops_rows_without_volume():
    rows = [_raw_row(), _raw_row(Volume=None, ProrationProduct="WATER", ActivityID=None)]

    result = transform_petrinex_data(_raw_frame(rows))

    # Administrative/proration rows carry no volume and are not production.
    assert len(result) == 1


def test_transform_flags_masked_volumes_instead_of_dropping_them():
    result = transform_petrinex_data(_raw_frame([_raw_row(Volume="***", ProductID="OIL")]))

    assert len(result) == 1
    assert bool(result.iloc[0]["volume_masked"]) is True
    assert pd.isna(result.iloc[0]["volume"])


def test_transform_keeps_negative_volumes():
    # Negative volumes are legitimate adjustments in Petrinex facility data.
    result = transform_petrinex_data(_raw_frame([_raw_row(Volume="-42.5", ActivityID="DIFF")]))

    assert result.iloc[0]["volume"] == -42.5


def test_transform_fills_null_from_to_id():
    result = transform_petrinex_data(_raw_frame([_raw_row(FromToID=None)]))

    # NULLs never compare equal in a unique index, so the key uses ''.
    assert result.iloc[0]["from_to_id"] == ""


def test_transform_deduplicates_on_natural_key():
    rows = [_raw_row(Volume="***"), _raw_row(Volume="954.1")]

    result = transform_petrinex_data(_raw_frame(rows))

    assert len(result) == 1
    # The real reported value wins over the masked duplicate.
    assert result.iloc[0]["volume"] == 954.1


def test_transform_rejects_file_missing_expected_columns():
    with pytest.raises(ValueError, match="missing expected columns"):
        transform_petrinex_data(pd.DataFrame({"ProductionMonth": ["2026-03"]}))


def test_transform_output_is_unique_on_natural_key():
    rows = [
        _raw_row(ProductID="GAS"),
        _raw_row(ProductID="OIL"),
        _raw_row(ActivityID="DISP", ProductID="GAS"),
    ]

    result = transform_petrinex_data(_raw_frame(rows))

    assert len(result) == 3
    assert not result.duplicated(subset=NATURAL_KEY).any()


def test_download_month_rejects_non_zip_response(monkeypatch, tmp_path):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield b"<html>Not published yet</html>"

    monkeypatch.setattr(
        petrinex.requests, "get", lambda url, timeout, stream: FakeResponse()
    )

    with pytest.raises(RuntimeError, match="not a zip archive"):
        petrinex.download_month("2026-03", data_dir=str(tmp_path))

    assert not list(tmp_path.glob("*.part"))


def test_download_month_saves_archive(monkeypatch, tmp_path):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("Vol.csv", "ProductionMonth\n2026-03\n")
    data = payload.getvalue()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield data

    monkeypatch.setattr(
        petrinex.requests, "get", lambda url, timeout, stream: FakeResponse()
    )

    result = petrinex.download_month("2026-03", data_dir=str(tmp_path))

    assert result.exists()
    assert zipfile.is_zipfile(result)
