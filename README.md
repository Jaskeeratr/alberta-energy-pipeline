# Alberta Energy Pipeline

[![CI](https://github.com/Jaskeeratr/alberta-energy-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/Jaskeeratr/alberta-energy-pipeline/actions/workflows/ci.yml)

An Airflow-orchestrated ETL pipeline that extracts Alberta Energy Regulator (AER)
crude oil production data from Excel workbooks, transforms report-style tables
into analysis-ready records, loads them into PostgreSQL, and supports Power BI
dashboarding.

This project is being built as a data engineering portfolio project. The current
version focuses on clean crude oil and natural gas ETL paths, optional automated
source downloads from the AER website, a dedicated validation step, incremental
upsert loading, pipeline audit tracking, Dockerized Airflow orchestration,
PostgreSQL storage, automated tests with CI, query benchmarking support, and a
Power BI dashboard file.

## Tech Stack

- Python
- pandas
- openpyxl
- SQLAlchemy
- PostgreSQL
- dbt (dbt-postgres)
- Apache Airflow
- Docker / Docker Compose
- Power BI

## Architecture

```text
AER website (optional automated download)
        |
        v
scripts/download.py
        |
        v
AER Excel workbooks in data/raw/
        |
        v
scripts/extract.py
        |
        v
scripts/transform.py
        |
        v
scripts/validate.py
        |
        v
scripts/load.py
        |
        v
PostgreSQL production tables
        |
        v
dbt models (analytics schema)
        |
        v
Power BI dashboard
```

The same ETL path can be run directly with Python or scheduled through the
Airflow DAG in `dags/energy_pipeline.py`.

## Data Source

The raw input files are AER Alberta energy Excel workbooks stored under
`data/raw/`. They come from the AER ST98 (Alberta Energy Outlook) statistical
data downloads.

The pipeline can also fetch the latest workbooks itself:

- Run `python run_pipeline.py --download` locally, or
- Set `AER_AUTO_DOWNLOAD=true` in `.env` so the Airflow DAG's
  `download_source_data` task refreshes the workbooks before each run.

The download URLs default to the ST98 2025 edition and can be overridden with
`CRUDE_OIL_XLSX_URL` and `NATURAL_GAS_XLSX_URL` when AER publishes a new
edition. Downloads are written atomically and sanity-checked, so a failed or
moved URL never corrupts the existing workbooks.

Current pipeline support:

- `crude_oil_production.xlsx`
  - Reads the `Tables` sheet.
  - Extracts Table S4.1.
  - Converts report-style crude oil production rows into normalized records.
- `natural_gas_production.xlsx`
  - Reads the `Tables` sheet.
  - Extracts Table S5.1.
  - Converts marketable natural gas production rows into normalized records.

### Petrinex facility volumetrics

The AER workbooks are summary tables (45 records per run). For volume, the
pipeline also loads [Petrinex](https://www.petrinex.ca/public-data/) Alberta
monthly conventional volumetric data: every reporting facility in the province,
roughly **520,000 records per production month**.

```bash
# Load a single month
python run_pipeline.py --source petrinex --months 2026-03

# Backfill several months
python run_pipeline.py --source petrinex --months 2026-01,2026-02,2026-03
```

Each month is tracked as its own `pipeline_runs` record, so a backfill is
auditable month by month rather than as one opaque run.

## Pipeline Flow

1. **Extract Excel data**
   - Loads the `Tables` sheet from each supported workbook.
   - Preserves the raw report layout so the transform step can locate the target
     table.
   - Parses each workbook once using a Rust-backed reader, which cut extraction
     from 53.3s to 0.18s per run (see [docs/performance.md](docs/performance.md)).

2. **Transform report-style tables**
   - Finds Table S4.1 for crude oil and Table S5.1 for natural gas.
   - Reads production categories and year columns.
   - Converts values into one record per category and production year.

3. **Validate records**
   - Confirms required fields are present.
   - Rejects invalid dates, invalid production values, negative values, missing
     categories, and duplicate records.
   - Prints a validation summary before loading.

4. **Track audit results**
   - Creates a pipeline run record.
   - Stores validation issues for rejected rows.
   - Updates run status, row counts, and error details when the run completes.

5. **Load into PostgreSQL**
   - Connects using environment variables from `.env`.
   - Performs incremental upserts keyed on field, operator, and production
     date: new records are inserted, existing records get their volume
     refreshed, and history from earlier editions is preserved.
   - Uses chunked batches through SQLAlchemy.

6. **Model analytics tables with dbt**
   - Staging views clean and type the raw production tables.
   - `analytics.fct_production` unifies oil and gas records with an
     `energy_source` column.
   - `analytics.yearly_production_summary` aggregates per-source, per-year
     totals for dashboarding.
   - dbt tests enforce not-null columns, accepted source values, natural-key
     uniqueness, and non-negative volumes.

7. **Visualize in Power BI**
   - The repository includes `dashboard/energy_dashboard.pbix`.
   - Dashboard screenshots will be added in a later polish phase.

## Folder Structure

```text
.
├── dags/                  # Airflow DAG
├── dashboard/             # Power BI dashboard file
├── data/raw/              # Source Excel workbooks
├── dbt/                   # dbt analytics models and data tests
├── reports/               # Generated benchmark reports
├── scripts/               # Download, extract, transform, validate, and load scripts
├── sql/                   # PostgreSQL schema
├── tests/                 # Pytest test suite
├── .env.example           # Example local environment variables
├── docker-compose.yaml    # Local Airflow container setup
├── Dockerfile             # Airflow image with Python dependencies
├── requirements.txt       # Python package dependencies
└── run_pipeline.py        # Local ETL entrypoint
```

## Local Setup

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Set a real PostgreSQL password in `.env`:

```text
POSTGRES_PASSWORD=your_password_here
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run automated tests with the coverage gate CI enforces:

```bash
pytest --cov=scripts --cov-fail-under=85
```

Generate a query benchmark report after PostgreSQL has been loaded:

```bash
python -m scripts.benchmark_queries
```

Measure extraction performance:

```bash
python -m scripts.benchmark_extract --runs 3
```

Create the database schema in PostgreSQL:

```bash
psql -d energy_pipeline -f sql/schema.sql
```

Run the local pipeline:

```bash
python run_pipeline.py
```

Useful variations:

```bash
# Download the latest AER workbooks first, then run everything
python run_pipeline.py --download

# Run a single source
python run_pipeline.py --source crude_oil
python run_pipeline.py --source natural_gas
```

## Docker and Airflow

The Docker setup runs two services:

- `postgres`: PostgreSQL 16 with a persistent named volume. On first startup it
  automatically creates the pipeline tables from `sql/schema.sql`.
- `airflow`: Airflow standalone with the project folders mounted in. It waits
  for the PostgreSQL healthcheck before starting and reaches the database at
  the compose-internal hostname `postgres` by default.

From your host machine (running `run_pipeline.py`, `psql`, dbt, or Power BI),
connect to the bundled database at `localhost:5432`.

If you prefer to run your own PostgreSQL on the host instead, set this in
`.env` so the Airflow container can reach it:

```text
POSTGRES_HOST=host.docker.internal
```

Start everything:

```bash
docker compose up --build
```

Then open Airflow at:

```text
http://localhost:8080
```

Default local Airflow credentials from `docker-compose.yaml`:

```text
Username: airflow
Password: airflow
```

Run the `alberta_energy_pipeline` DAG to execute the crude oil and natural gas
ETL pipelines. The DAG runs a `download_source_data` task first (a no-op unless
`AER_AUTO_DOWNLOAD=true`), then the two source ETL tasks in parallel.

## PostgreSQL Schema

Current tables:

### `oil_production`

| Column | Purpose |
| --- | --- |
| `id` | Surrogate primary key |
| `field_name` | Crude oil production category from the AER table |
| `operator` | Source/operator label |
| `production_date` | Production year stored as a date |
| `volume_m3` | Production value converted to cubic metres per day |
| `province` | Defaults to `AB` |
| `loaded_at` | Timestamp when the row was loaded |

Indexes exist on `field_name` and `production_date`, plus a unique index on
`(field_name, operator, production_date)` that backs the incremental upsert.

### `gas_production`

| Column | Purpose |
| --- | --- |
| `id` | Surrogate primary key |
| `field_name` | Natural gas production category from the AER table |
| `operator` | Source/operator label |
| `production_date` | Production year stored as a date |
| `volume_m3` | Production value converted to cubic metres per day |
| `province` | Defaults to `AB` |
| `loaded_at` | Timestamp when the row was loaded |

Indexes exist on `field_name` and `production_date`, plus a unique index on
`(field_name, operator, production_date)` that backs the incremental upsert.

If you created the tables before the upsert change, re-run
`psql -d energy_pipeline -f sql/schema.sql` once to add the unique indexes —
every statement in the schema file is idempotent.

### `pipeline_runs`

Tracks each ETL run by source name, start and finish time, status, row counts,
rejected rows, error rate, and failure message.

### `data_quality_issues`

Stores rejected validation records by pipeline run, source name, row identifier,
issue type, and issue detail.

## Analytics Layer (dbt)

The `dbt/` project builds an `analytics` schema on top of the loaded tables:

| Model | Type | Purpose |
| --- | --- | --- |
| `stg_oil_production` | view | Cleaned crude oil records with a derived year |
| `stg_gas_production` | view | Cleaned natural gas records with a derived year |
| `fct_production` | table | Unified oil + gas fact table with `energy_source` |
| `yearly_production_summary` | table | Per-source, per-year aggregates |

Install the dbt dependencies (kept out of the main requirements so the Airflow
image stays small):

```bash
pip install -r requirements-dbt.txt
```

Build the models and run all dbt data tests (uses the same `POSTGRES_*`
environment variables as the pipeline):

```bash
dbt build --project-dir dbt --profiles-dir dbt
```

Point Power BI at the `analytics` schema tables instead of the raw ones.

## Performance

Extraction was profiled and optimized; full methodology and results are in
[docs/performance.md](docs/performance.md).

| Metric | Value |
| --- | --- |
| AER extraction time per run | 53.27s to 0.18s (~299x faster) |
| Petrinex month processed | 549,016 raw rows to 523,248 records in ~5s |
| Test suite | 75 tests, 91% coverage of `scripts/` |
| Coverage gate enforced in CI | 85% minimum |

Petrinex months are loaded with PostgreSQL `COPY` into a temporary table
followed by a single set-based `INSERT ... ON CONFLICT` merge. Half a million
statement-per-row upserts would dominate the run; staging and merging in one
pass keeps the load to a single bulk operation.

## Continuous Integration

Every push runs two GitHub Actions jobs:

- `test`: the pytest unit suite, gated at 85% coverage.
- `integration`: spins up PostgreSQL 16, creates the schema, runs the full
  AER ETL end to end, downloads and loads a real Petrinex month (about 520,000
  records), reruns both to prove the upserts are idempotent, asserts the loaded
  row count, then runs `dbt build` including all dbt data tests.

## Dashboard

The Power BI file is stored at:

```text
dashboard/energy_dashboard.pbix
```

Screenshots are not included yet. Real dashboard and Airflow images should be
added under `docs/screenshots/` after the tools are run locally.

Screenshot guidance is available in:

```text
docs/screenshots/README.md
```

## Query Benchmarking

The repository includes `scripts/benchmark_queries.py` for generating real
PostgreSQL `EXPLAIN ANALYZE` output. The report path is:

```text
reports/query_benchmark.md
```

The checked-in report is currently a placeholder because benchmark queries have
not been run against a loaded PostgreSQL database in this environment. No
performance improvement percentages are claimed.

## Current Limitations

- The AER summary tables are small: a full run loads 45 production records
  (25 crude oil, 20 natural gas). Volume-based claims come from the Petrinex
  facility data instead.
- Query benchmark tooling exists, but real timing results must be generated from
  a loaded PostgreSQL database before making performance claims.
- Dashboard screenshots are not included yet.

## Planned Improvements

- Add Power BI and Airflow screenshots for GitHub presentation.
- Run the benchmark script against a loaded PostgreSQL database and commit the
  real report output.

## Project Impact

This project demonstrates a practical batch data engineering workflow:
extracting messy Excel-based public energy data, transforming report-style
tables into normalized records, validating production data, loading PostgreSQL
tables, tracking audit results, and supporting dashboard analysis.

The strongest portfolio signal is not a fake scale claim. It is the combination
of orchestration, schema design, validation, auditability, tests, and honest
documentation.

## What I Learned

- How to convert report-style Excel tables into analysis-ready records.
- How to separate extraction, transformation, validation, loading, and auditing
  into readable pipeline steps.
- How to keep resume claims defensible by tying them to real repo features.
- How to document limitations without weakening the project.

## Safe Resume Claims

- Built an Airflow-orchestrated ETL pipeline for Alberta crude oil and natural
  gas production data.
- Transformed AER Excel workbook tables into normalized PostgreSQL reporting
  tables.
- Added validation checks for missing fields, invalid dates, negative values,
  invalid production values, and duplicate records.
- Implemented pipeline run tracking and data quality issue logging.
- Implemented incremental upsert loading with a natural-key unique index.
- Automated source data downloads from the AER website with atomic writes and
  payload sanity checks.
- Profiled and optimized the extraction step, reducing it from 53.3s to 0.18s
  per run (~299x) with output verified identical.
- Added automated pytest coverage for core ETL behavior (38 tests, 89%
  coverage), enforced by an 85% CI gate on every push.
- Modeled an analytics layer with dbt (staging views, a unified fact table,
  yearly aggregates, monthly product totals, operator league tables) with dbt
  data tests.
- Ingested Petrinex Alberta facility volumetric data at roughly 520,000 records
  per production month using PostgreSQL COPY staging plus a set-based merge,
  with month-by-month backfill and audit tracking.
- Added an end-to-end CI integration job that loads a real PostgreSQL database
  and verifies upsert idempotency and all dbt tests.
- Dockerized the full stack: Airflow plus PostgreSQL with schema auto-creation
  and healthcheck-gated startup.

## Claims to Avoid

- Do not claim a specific record count until it is measured from a real run.
- Do not claim a specific validation error rate until it appears in
  `pipeline_runs`.
- Do not claim a query performance improvement percentage until
  `reports/query_benchmark.md` contains real `EXPLAIN ANALYZE` output.
- Do not claim cloud deployment, streaming, Spark, Kafka, or machine learning.

## Final Quality Check

A fuller project review is available in:

```text
docs/final_quality_check.md
```

## Resume-Safe Summary

Built a Python ETL pipeline for Alberta crude oil and natural gas production data
using pandas, PostgreSQL, Docker, Airflow, and Power BI. The project extracts AER
Excel data, transforms report-style tables into normalized production records,
validates the cleaned datasets, tracks pipeline audit results, loads valid
records into PostgreSQL, includes automated tests, and supports dashboard
reporting.
