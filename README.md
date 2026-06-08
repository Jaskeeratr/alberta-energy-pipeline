# Alberta Energy Pipeline

An Airflow-orchestrated ETL pipeline that extracts Alberta Energy Regulator (AER)
crude oil production data from Excel workbooks, transforms report-style tables
into analysis-ready records, loads them into PostgreSQL, and supports Power BI
dashboarding.

This project is being built as a data engineering portfolio project. The current
version focuses on clean crude oil and natural gas ETL paths, a dedicated
validation step, pipeline audit tracking, Dockerized Airflow orchestration,
PostgreSQL storage, automated tests, query benchmarking support, and a Power BI
dashboard file.

## Tech Stack

- Python
- pandas
- openpyxl
- SQLAlchemy
- PostgreSQL
- Apache Airflow
- Docker / Docker Compose
- Power BI

## Architecture

```text
AER Excel workbooks
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
Power BI dashboard
```

The same ETL path can be run directly with Python or scheduled through the
Airflow DAG in `dags/energy_pipeline.py`.

## Data Source

The raw input files are AER Alberta energy Excel workbooks stored under
`data/raw/`.

Current pipeline support:

- `crude_oil_production.xlsx`
  - Reads the `Tables` sheet.
  - Extracts Table S4.1.
  - Converts report-style crude oil production rows into normalized records.
- `natural_gas_production.xlsx`
  - Reads the `Tables` sheet.
  - Extracts Table S5.1.
  - Converts marketable natural gas production rows into normalized records.

## Pipeline Flow

1. **Extract Excel data**
   - Loads the `Tables` sheet from each supported workbook.
   - Preserves the raw report layout so the transform step can locate the target
     table.

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
   - Truncates and reloads the relevant production table.
   - Uses batched inserts through pandas and SQLAlchemy.

6. **Visualize in Power BI**
   - The repository includes `dashboard/energy_dashboard.pbix`.
   - Dashboard screenshots will be added in a later polish phase.

## Folder Structure

```text
.
├── dags/                  # Airflow DAG
├── dashboard/             # Power BI dashboard file
├── data/raw/              # Source Excel workbooks
├── reports/               # Generated benchmark reports
├── scripts/               # Extract, transform, validate, and load scripts
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

Run automated tests:

```bash
pytest
```

Generate a query benchmark report after PostgreSQL has been loaded:

```bash
python scripts/benchmark_queries.py
```

Create the database schema in PostgreSQL:

```bash
psql -d energy_pipeline -f sql/schema.sql
```

Run the local pipeline:

```bash
python run_pipeline.py
```

## Docker and Airflow

The Docker setup runs Airflow and mounts the project folders into the container.
PostgreSQL is expected to be available separately.

If PostgreSQL runs on your host machine, use this in `.env`:

```text
POSTGRES_HOST=host.docker.internal
```

Start Airflow:

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
ETL pipelines.

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

Indexes currently exist on `field_name` and `production_date`.

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

Indexes currently exist on `field_name` and `production_date`.

### `pipeline_runs`

Tracks each ETL run by source name, start and finish time, status, row counts,
rejected rows, error rate, and failure message.

### `data_quality_issues`

Stores rejected validation records by pipeline run, source name, row identifier,
issue type, and issue detail.

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

- Query benchmark tooling exists, but real timing results must be generated from
  a loaded PostgreSQL database before making performance claims.
- Dashboard screenshots are not included yet.

## Planned Improvements

- Add Power BI and Airflow screenshots for GitHub presentation.
- Run the benchmark script against a loaded PostgreSQL database and commit the
  real report output.
- Add a Dockerized PostgreSQL service or seed/demo workflow for easier local
  reproduction.

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
- Added automated pytest coverage for core ETL behavior.

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
