import os
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


def load_oil_data(df: pd.DataFrame) -> None:
    """
    Load cleaned oil production data into PostgreSQL.
    Uses bulk insert for performance.
    """

    print("Connecting to PostgreSQL...")

    engine = create_engine(get_database_url())

    # Optional: clear table before loading
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE oil_production RESTART IDENTITY"))

    print("Loading data into database...")

    df.to_sql(
        name="oil_production",
        con=engine,
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi"
    )

    print(f"Loaded {len(df)} rows into oil_production table")
