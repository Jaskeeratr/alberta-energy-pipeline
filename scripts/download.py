import os
from pathlib import Path

import requests


# AER publishes the ST98 statistical workbooks at year-stamped URLs.
# Override these with CRUDE_OIL_XLSX_URL / NATURAL_GAS_XLSX_URL when a new
# ST98 edition is released.
DEFAULT_SOURCE_URLS = {
    "crude_oil": (
        "https://documents.aer.ca/sts/st98/2025/"
        "st98-2025-crude-oil-supplydemand-data.xlsx"
    ),
    "natural_gas": (
        "https://documents.aer.ca/sts/st98/2025/"
        "st98-2025-naturalgas-supplydemand-data.xlsx"
    ),
}

SOURCE_URL_ENV_VARS = {
    "crude_oil": "CRUDE_OIL_XLSX_URL",
    "natural_gas": "NATURAL_GAS_XLSX_URL",
}

SOURCE_FILENAMES = {
    "crude_oil": "crude_oil_production.xlsx",
    "natural_gas": "natural_gas_production.xlsx",
}

XLSX_MAGIC_BYTES = b"PK"  # .xlsx files are zip archives


def get_source_url(source_name: str) -> str:
    """Return the download URL for a source, honoring env var overrides."""
    if source_name not in DEFAULT_SOURCE_URLS:
        raise ValueError(f"Unknown source: {source_name}")

    env_var = SOURCE_URL_ENV_VARS[source_name]
    return os.getenv(env_var) or DEFAULT_SOURCE_URLS[source_name]


def download_source_file(url: str, dest_path: str, timeout: int = 60) -> Path:
    """
    Download one workbook to dest_path.

    Writes to a temporary file first so a failed download never clobbers an
    existing good workbook, and sanity-checks that the payload looks like a
    real .xlsx file rather than an HTML error page.
    """
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".part")

    print(f"Downloading {url}")
    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    first_chunk = b""
    with open(tmp_path, "wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if not first_chunk:
                first_chunk = chunk
            fh.write(chunk)

    if not first_chunk.startswith(XLSX_MAGIC_BYTES):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded content from {url} does not look like an .xlsx file. "
            "The URL may have moved to a new ST98 edition."
        )

    tmp_path.replace(dest)
    size_kb = dest.stat().st_size / 1024
    print(f"Saved {dest} ({size_kb:,.0f} KB)")
    return dest


def download_source_data(data_dir: str = "data/raw") -> dict:
    """
    Download all supported AER workbooks into data_dir.

    Returns a mapping of source name to the downloaded file path.
    """
    downloaded = {}
    for source_name, filename in SOURCE_FILENAMES.items():
        url = get_source_url(source_name)
        dest_path = str(Path(data_dir) / filename)
        downloaded[source_name] = str(download_source_file(url, dest_path))
    return downloaded


def maybe_download_source_data(data_dir: str = "data/raw") -> bool:
    """
    Download workbooks only when AER_AUTO_DOWNLOAD is enabled.

    Keeps scheduled runs offline-friendly by default: the pipeline falls back
    to the workbooks already committed under data/raw.
    """
    enabled = os.getenv("AER_AUTO_DOWNLOAD", "false").strip().lower()
    if enabled not in ("1", "true", "yes"):
        print("AER_AUTO_DOWNLOAD is not enabled; using existing local workbooks.")
        return False

    download_source_data(data_dir)
    return True
