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


def _load_production_data(df: pd.DataFrame, table_name: str) -> None:
    print("Connecting to PostgreSQL...")

    engine = create_engine(get_database_url())

    try:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY"))

        print("Loading data into database...")

        df.to_sql(
            name=table_name,
            con=engine,
            if_exists="append",
            index=False,
            chunksize=1000,
            method="multi"
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load data into {table_name}: {exc}") from exc

    print(f"Loaded {len(df)} rows into {table_name} table")


def load_oil_data(df: pd.DataFrame) -> None:
    """
    Load cleaned oil production data into PostgreSQL.
    Uses bulk insert for performance.
    """
    _load_production_data(df, "oil_production")


def load_gas_data(df: pd.DataFrame) -> None:
    """
    Load cleaned natural gas production data into PostgreSQL.
    Uses bulk insert for performance.
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
