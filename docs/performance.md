# Extraction Performance

Measured results for the Excel extraction step, produced by
`scripts/benchmark_extract.py`. Rerun it any time with:

```bash
python -m scripts.benchmark_extract --runs 3
```

## Results

Environment: Windows 11, Python 3.12.10, pandas 2.x, 3 timed runs per variant.

| Source | Before | After | Speedup |
| --- | ---: | ---: | ---: |
| `crude_oil_production.xlsx` (1.9 MB) | 36.184 s | 0.110 s | 327.9x |
| `natural_gas_production.xlsx` (1.6 MB) | 17.085 s | 0.068 s | 249.8x |
| **Combined per pipeline run** | **53.27 s** | **0.18 s** | **~299x** |

Extraction went from roughly 53 seconds per run to under a fifth of a second,
a 99.7% reduction in extraction time.

## What changed

Two independent problems, fixed together.

### 1. The workbook was parsed twice

The original implementation opened the workbook to list its sheet names, then
opened the same file a second time to read the data:

```python
excel_file = pd.ExcelFile(path)          # full parse #1
print("Available sheets:", excel_file.sheet_names)
df = pd.read_excel(path, sheet_name="Tables", header=None)   # full parse #2
```

Reusing the already-open handle removes the duplicate parse and alone
accounts for a ~2x improvement.

### 2. openpyxl is slow on these workbooks

These AER workbooks are report-style files carrying many sheets, merged
cells, and formatting. openpyxl parses all of it in Python even though the
pipeline only needs one sheet. Switching to `python-calamine`, a Rust-backed
reader supported by pandas, accounts for the remaining two orders of
magnitude.

The fast engine is optional: `scripts/extract.py` falls back to pandas'
default engine if `python-calamine` is unavailable, so the pipeline still
runs without it.

## Correctness

A speedup only counts if the output is unchanged. Both readers were compared
with `pandas.testing.assert_frame_equal` on the raw extracted frames and again
on the transformed records:

- `crude_oil`: raw frames identical at (41, 54); transformed records identical at 25 rows.
- `natural_gas`: raw frames identical at (40, 74); transformed records identical at 20 rows.

`scripts/benchmark_extract.py` also compares output shapes on every run and
prints a warning if they ever diverge.

## Note on query benchmarks

`reports/query_benchmark.md` covers PostgreSQL query timings and is a
separate concern. Those numbers are not meaningful at the current data volume:
the production tables hold 45 rows total, so PostgreSQL sequential-scans them
regardless of indexing. No query performance claims should be made until the
pipeline loads a substantially larger dataset.
