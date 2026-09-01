import io
import os
import json
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text


def get_database_url() -> str:
    """
    Build the PostgreSQL connection URL from environment variables.
    DATABASE_URL can be used to override the individual POSTGRES_* settings.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "energy_pipeline")

    if not password:
        raise RuntimeError(
            "Missing database password. Set POSTGRES_PASSWORD or DATABASE_URL."
        )

    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


PRODUCTION_COLUMNS = ["field_name", "operator", "production_date", "volume_m3"]

UPSERT_CHUNK_SIZE = 1000


def _build_upsert_statement(table_name: str):
    """
    Incremental upsert keyed on (field_name, operator, production_date).

    New records are inserted; records already present get their volume and
    loaded_at refreshed. Historical rows from earlier editions of the source
    workbook are preserved instead of being truncated away.
    """
    return text(
        f"""
        INSERT INTO {table_name} (field_name, operator, production_date, volume_m3)
        VALUES (:field_name, :operator, :production_date, :volume_m3)
        ON CONFLICT (field_name, operator, production_date)
        DO UPDATE SET
            volume_m3 = EXCLUDED.volume_m3,
            loaded_at = NOW()
        """
    )


def _load_production_data(df: pd.DataFrame, table_name: str) -> None:
    if df.empty:
        print(f"No valid rows to load into {table_name}; skipping load step.")
        return

    print("Connecting to PostgreSQL...")

    engine = create_engine(get_database_url())
    statement = _build_upsert_statement(table_name)
    rows = df[PRODUCTION_COLUMNS].to_dict("records")

    try:
        with engine.begin() as conn:
            for start in range(0, len(rows), UPSERT_CHUNK_SIZE):
                conn.execute(statement, rows[start:start + UPSERT_CHUNK_SIZE])
    except Exception as exc:
        raise RuntimeError(f"Failed to load data into {table_name}: {exc}") from exc

    print(f"Upserted {len(rows)} rows into {table_name} table")


def load_oil_data(df: pd.DataFrame) -> None:
    """
    Load cleaned oil production data into PostgreSQL.
    Uses chunked incremental upserts keyed on field, operator, and date.
    """
    _load_production_data(df, "oil_production")


def load_gas_data(df: pd.DataFrame) -> None:
    """
    Load cleaned natural gas production data into PostgreSQL.
    Uses chunked incremental upserts keyed on field, operator, and date.
    """
    _load_production_data(df, "gas_production")


def create_pipeline_run(source_name: str) -> int:
    """Create an audit record for a pipeline run and return its run_id."""
    engine = create_engine(get_database_url())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO pipeline_runs (source_name, status)
                VALUES (:source_name, 'running')
                RETURNING run_id
                """
            ),
            {"source_name": source_name},
        )
        return int(result.scalar_one())


def finish_pipeline_run(
    run_id: int,
    status: str,
    rows_extracted: int = 0,
    rows_loaded: int = 0,
    rows_rejected: int = 0,
    error_rate: float = 0.0,
    error_message: str | None = None,
) -> None:
    """Update an audit record when a pipeline run finishes or fails."""
    engine = create_engine(get_database_url())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE pipeline_runs
                SET finished_at = NOW(),
                    status = :status,
                    rows_extracted = :rows_extracted,
                    rows_loaded = :rows_loaded,
                    rows_rejected = :rows_rejected,
                    error_rate = :error_rate,
                    error_message = :error_message
                WHERE run_id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "rows_extracted": rows_extracted,
                "rows_loaded": rows_loaded,
                "rows_rejected": rows_rejected,
                "error_rate": error_rate,
                "error_message": error_message,
            },
        )


def load_data_quality_issues(
    run_id: int,
    source_name: str,
    rejected_df: pd.DataFrame,
) -> None:
    """Store validation issues for rejected records."""
    if rejected_df.empty:
        return

    issue_rows = []
    for row_index, row in rejected_df.iterrows():
        issue_types = str(row.get("validation_errors", "unknown_error")).split(";")
        issue_detail = json.dumps(row.to_dict(), default=str)
        for issue_type in issue_types:
            issue_rows.append(
                {
                    "pipeline_run_id": run_id,
                    "source_name": source_name,
                    "row_identifier": str(row_index),
                    "issue_type": issue_type,
                    "issue_detail": issue_detail,
                }
            )

    if not issue_rows:
        return

    engine = create_engine(get_database_url())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO data_quality_issues (
                    pipeline_run_id,
                    source_name,
                    row_identifier,
                    issue_type,
                    issue_detail
                )
                VALUES (
                    :pipeline_run_id,
                    :source_name,
                    :row_identifier,
                    :issue_type,
                    :issue_detail
                )
                """
            ),
            issue_rows,
        )


FACILITY_COLUMNS = [
    "production_month",
    "operator_ba_id",
    "operator_name",
    "facility_id",
    "facility_type",
    "facility_subtype_desc",
    "facility_name",
    "facility_location",
    "activity_id",
    "product_id",
    "from_to_id",
    "volume",
    "energy",
    "hours",
    "volume_masked",
]


def load_facility_production(df: pd.DataFrame) -> int:
    """
    Bulk load Petrinex facility production records.

    A month is roughly half a million rows, which is far too many for
    statement-per-row upserts. Instead the batch is streamed into an unlogged
    temporary table with COPY and merged in a single set-based statement, so
    the whole month costs one pass rather than 500,000 round trips.

    Returns the number of rows staged for the merge.
    """
    if df.empty:
        print("No facility rows to load; skipping load step.")
        return 0

    staged = df.reindex(columns=FACILITY_COLUMNS)

    buffer = io.StringIO()
    staged.to_csv(buffer, index=False, header=False, na_rep=r"\N")
    buffer.seek(0)

    column_list = ", ".join(FACILITY_COLUMNS)

    try:
        engine = create_engine(get_database_url())
        with engine.begin() as conn:
            raw_conn = conn.connection
            with raw_conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TEMP TABLE tmp_facility_production
                    (LIKE facility_production INCLUDING DEFAULTS)
                    ON COMMIT DROP
                    """
                )
                cursor.copy_expert(
                    f"COPY tmp_facility_production ({column_list}) "
                    r"FROM STDIN WITH (FORMAT csv, NULL '\N')",
                    buffer,
                )
                cursor.execute(
                    f"""
                    INSERT INTO facility_production ({column_list})
                    SELECT {column_list} FROM tmp_facility_production
                    ON CONFLICT (production_month, facility_id, activity_id,
                                 product_id, from_to_id)
                    DO UPDATE SET
                        volume = EXCLUDED.volume,
                        energy = EXCLUDED.energy,
                        hours = EXCLUDED.hours,
                        volume_masked = EXCLUDED.volume_masked,
                        operator_name = EXCLUDED.operator_name,
                        loaded_at = NOW()
                    """
                )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load data into facility_production: {exc}"
        ) from exc

    print(f"Upserted {len(staged):,} rows into facility_production table")
    return len(staged)
