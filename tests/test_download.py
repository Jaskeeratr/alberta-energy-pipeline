import pytest

from scripts import download


class FakeResponse:
    def __init__(self, content=b"PK\x03\x04fake-xlsx-bytes", status_ok=True):
        self.content = content
        self.status_ok = status_ok

    def raise_for_status(self):
        if not self.status_ok:
            raise RuntimeError("404 Client Error")

    def iter_content(self, chunk_size):
        yield self.content


def test_get_source_url_uses_env_override(monkeypatch):
    monkeypatch.setenv("CRUDE_OIL_XLSX_URL", "https://example.com/custom.xlsx")

    assert download.get_source_url("crude_oil") == "https://example.com/custom.xlsx"


def test_get_source_url_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("NATURAL_GAS_XLSX_URL", raising=False)

    assert "documents.aer.ca" in download.get_source_url("natural_gas")


def test_get_source_url_rejects_unknown_source():
    with pytest.raises(ValueError, match="Unknown source"):
        download.get_source_url("coal")


def test_download_writes_workbook_to_destination(monkeypatch, tmp_path):
    monkeypatch.setattr(
        download.requests,
        "get",
        lambda url, timeout, stream: FakeResponse(),
    )

    dest = tmp_path / "crude_oil_production.xlsx"
    result = download.download_source_file("https://example.com/data.xlsx", str(dest))

    assert result == dest
    assert dest.read_bytes().startswith(b"PK")
    assert not dest.with_suffix(".xlsx.part").exists()


def test_download_rejects_non_xlsx_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(
        download.requests,
        "get",
        lambda url, timeout, stream: FakeResponse(content=b"<html>Not Found</html>"),
    )

    dest = tmp_path / "crude_oil_production.xlsx"
    with pytest.raises(RuntimeError, match="does not look like an .xlsx file"):
        download.download_source_file("https://example.com/data.xlsx", str(dest))

    assert not dest.exists()
    assert not dest.with_suffix(".xlsx.part").exists()


def test_maybe_download_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AER_AUTO_DOWNLOAD", raising=False)

    def fail_download(data_dir):
        raise AssertionError("Download should not run when disabled")

    monkeypatch.setattr(download, "download_source_data", fail_download)

    assert download.maybe_download_source_data() is False


def test_maybe_download_runs_when_enabled(monkeypatch):
    monkeypatch.setenv("AER_AUTO_DOWNLOAD", "true")
    calls = []
    monkeypatch.setattr(
        download,
        "download_source_data",
        lambda data_dir: calls.append(data_dir),
    )

    assert download.maybe_download_source_data("data/raw") is True
    assert calls == ["data/raw"]
