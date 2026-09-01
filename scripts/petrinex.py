"""
Petrinex Alberta monthly conventional volumetric data.

Petrinex publishes one archive per production month covering every reporting
facility in Alberta. A single month is roughly 550,000 rows, so this module is
built for bulk volume: it streams the download to disk and normalizes with
vectorized pandas operations rather than per-row Python.
"""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pandas as pd
import requests


PETRINEX_URL_TEMPLATE = (
    "https://www.petrinex.gov.ab.ca/publicdata/API/Files/AB/Vol/{month}/CSV"
)

# Petrinex masks confidential values with three asterisks rather than leaving
# them blank. Coercing these to NaN silently would understate reported volumes,
# so they are tracked explicitly.
MASK_SENTINEL = "***"

# The natural key verified unique across a full month of unmasked records.
NATURAL_KEY = [
    "production_month",
    "facility_id",
    "activity_id",
    "product_id",
    "from_to_id",
]

COLUMN_MAP = {
    "ProductionMonth": "production_month",
    "OperatorBAID": "operator_ba_id",
    "OperatorName": "operator_name",
    "ReportingFacilityID": "facility_id",
    "ReportingFacilityType": "facility_type",
    "ReportingFacilitySubTypeDesc": "facility_subtype_desc",
    "ReportingFacilityName": "facility_name",
    "ReportingFacilityLocation": "facility_location",
    "ActivityID": "activity_id",
    "ProductID": "product_id",
    "FromToID": "from_to_id",
    "Volume": "volume",
    "Energy": "energy",
    "Hours": "hours",
}


def get_month_url(month: str) -> str:
    """Return the download URL for a YYYY-MM production month."""
    validate_month(month)
    override = os.getenv("PETRINEX_URL_TEMPLATE") or PETRINEX_URL_TEMPLATE
    return override.format(month=month)


def validate_month(month: str) -> None:
    """Reject anything that is not a YYYY-MM production month."""
    parts = str(month).split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise ValueError(f"Expected a YYYY-MM production month, got: {month!r}")
    if not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"Expected a YYYY-MM production month, got: {month!r}")
    if not 1 <= int(parts[1]) <= 12:
        raise ValueError(f"Month must be between 01 and 12, got: {month!r}")


def download_month(month: str, data_dir: str = "data/raw/petrinex", timeout: int = 300) -> Path:
    """
    Download one production month archive.

    Streams to a temporary file so a failed download never leaves a partial
    archive in place.
    """
    validate_month(month)
    url = get_month_url(month)
    dest_dir = Path(data_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"Vol_{month}-AB.zip"
    tmp_path = dest.with_suffix(".zip.part")

    print(f"Downloading Petrinex {month} from {url}")
    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    with open(tmp_path, "wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            fh.write(chunk)

    if not zipfile.is_zipfile(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Petrinex response for {month} is not a zip archive. "
            "The month may not be published yet."
        )

    tmp_path.replace(dest)
    print(f"Saved {dest} ({dest.stat().st_size / 1024 / 1024:,.1f} MB)")
    return dest


def _read_nested_csv(archive_path: Path) -> pd.DataFrame:
    """
    Read the CSV out of a Petrinex archive.

    Petrinex nests the payload: the downloaded archive contains an inner
    ``.csv.zip`` which in turn holds the CSV itself.
    """
    with zipfile.ZipFile(archive_path) as outer:
        names = outer.namelist()

        inner_zips = [n for n in names if n.lower().endswith(".zip")]
        if inner_zips:
            with outer.open(inner_zips[0]) as inner_bytes:
                with zipfile.ZipFile(io.BytesIO(inner_bytes.read())) as inner:
                    csv_names = [n for n in inner.namelist() if n.lower().endswith(".csv")]
                    if not csv_names:
                        raise RuntimeError(f"No CSV inside {inner_zips[0]}")
                    with inner.open(csv_names[0]) as fh:
                        return pd.read_csv(fh, dtype=str, low_memory=False)

        csv_names = [n for n in names if n.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError(f"No CSV found in {archive_path}")
        with outer.open(csv_names[0]) as fh:
            return pd.read_csv(fh, dtype=str, low_memory=False)


def extract_petrinex_data(archive_path: str) -> pd.DataFrame:
    """Load the raw volumetric CSV from a downloaded Petrinex archive."""
    path = Path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {archive_path}")

    print(f"Extracting data from: {archive_path}")
    df = _read_nested_csv(path)
    print(f"Extracted {len(df):,} rows and {len(df.columns)} columns")
    return df


def transform_petrinex_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize raw Petrinex rows into facility production records.

    Keeps only rows that report a volume, records whether the volume was
    masked for confidentiality, and resolves the natural key so the load step
    can upsert safely.
    """
    print(f"Starting Petrinex transform with {len(df):,} rows")

    missing = [c for c in COLUMN_MAP if c not in df.columns]
    if missing:
        raise ValueError(f"Petrinex file is missing expected columns: {missing}")

    working = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()

    # Rows without a volume are proration/administrative records, not production.
    working = working[working["volume"].notna()].copy()

    volume_text = working["volume"].astype(str).str.strip()
    working["volume_masked"] = volume_text.eq(MASK_SENTINEL)

    working["volume"] = pd.to_numeric(
        volume_text.where(~working["volume_masked"]), errors="coerce"
    )
    for col in ["energy", "hours"]:
        working[col] = pd.to_numeric(
            working[col].astype(str).str.strip().replace(MASK_SENTINEL, None),
            errors="coerce",
        )

    # A month like "2026-03" becomes the first of that month so the column can
    # be a real DATE and join cleanly with the AER production tables.
    working["production_month"] = pd.to_datetime(
        working["production_month"] + "-01", errors="coerce"
    ).dt.date

    # from_to_id participates in the unique key, and NULLs never compare equal
    # in a Postgres unique index, so empty values become an empty string.
    working["from_to_id"] = working["from_to_id"].fillna("").astype(str).str.strip()
    for col in ["activity_id", "product_id"]:
        working[col] = working[col].fillna("").astype(str).str.strip()

    working = working[working["production_month"].notna()]
    working = working.drop_duplicates(subset=NATURAL_KEY, keep="last")

    print(
        f"Petrinex transform complete: {len(working):,} rows "
        f"({int(working['volume_masked'].sum()):,} masked volumes)"
    )
    return working.reset_index(drop=True)
