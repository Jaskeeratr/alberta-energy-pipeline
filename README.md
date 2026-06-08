# Alberta Energy Pipeline

An Airflow-orchestrated ETL pipeline that extracts Alberta Energy Regulator (AER)
crude oil production data from Excel workbooks, transforms report-style tables
into analysis-ready records, loads them into PostgreSQL, and supports Power BI
dashboarding.

This project is being built as a data engineering portfolio project. The current
version focuses on a clean crude oil ETL path, a dedicated validation step,
Dockerized Airflow orchestration, PostgreSQL storage, and a Power BI dashboard
file. Audit tracking, natural gas processing, tests, and benchmark reporting are
planned incremental upgrades.

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
AER Excel workbook
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
PostgreSQL oil_production table
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

Planned support:

- `natural_gas_production.xlsx`
  - The file is present, but natural gas records are not loaded yet.

## Pipeline Flow

1. **Extract Excel data**
   - Loads the `Tables` sheet from the crude oil workbook.
   - Preserves the raw report layout so the transform step can locate the target
     table.

2. **Transform report-style tables**
   - Finds Table S4.1 in the workbook.
   - Reads production categories and year columns.
   - Converts values into one record per category and production year.

3. **Validate records**
   - Confirms required fields are present.
   - Rejects invalid dates, invalid production values, negative values, missing
     categories, and duplicate records.
   - Prints a validation summary before loading.

4. **Load into PostgreSQL**
   - Connects using environment variables from `.env`.
   - Truncates and reloads the `oil_production` table.
   - Uses batched inserts through pandas and SQLAlchemy.

5. **Visualize in Power BI**
   - The repository includes `dashboard/energy_dashboard.pbix`.
   - Dashboard screenshots will be added in a later polish phase.

## Folder Structure

```text
.
├── dags/                  # Airflow DAG
├── dashboard/             # Power BI dashboard file
├── data/raw/              # Source Excel workbooks
├── scripts/               # Extract, transform, validate, and load scripts
├── sql/                   # PostgreSQL schema
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

Run the `alberta_energy_pipeline` DAG to execute the crude oil ETL pipeline.

## PostgreSQL Schema

Current table:

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

## Dashboard

The Power BI file is stored at:

```text
dashboard/energy_dashboard.pbix
```

Screenshots are not included yet. A later project polish phase will add dashboard
and Airflow screenshots under `docs/screenshots/`.

## Current Limitations

- Natural gas data exists in the repository but is not processed yet.
- There are no audit tables or pipeline run history yet.
- There are no automated tests yet.
- Query performance claims are not made because benchmark evidence has not been
  generated yet.
- Dashboard screenshots are not included yet.

## Planned Improvements

- Add audit tables for pipeline runs and data quality issues.
- Extend the ETL flow to process natural gas production data.
- Add pytest coverage for extract, transform, validation, and load behavior.
- Add query benchmarking with `EXPLAIN ANALYZE`.
- Add Power BI and Airflow screenshots for GitHub presentation.

## Resume-Safe Summary

Built a Python ETL pipeline for Alberta crude oil production data using pandas,
PostgreSQL, Docker, Airflow, and Power BI. The project extracts AER Excel data,
transforms report-style tables into normalized production records, validates the
cleaned dataset, loads valid records into PostgreSQL, and supports dashboard
reporting.
