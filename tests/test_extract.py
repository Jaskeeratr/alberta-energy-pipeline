import pytest

from scripts.extract import extract_oil_data


def test_extract_missing_file_raises_clear_error():
    with pytest.raises(FileNotFoundError, match="File not found"):
        extract_oil_data("data/raw/does_not_exist.xlsx")
