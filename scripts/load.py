import pandas as pd
from sqlalchemy import create_engine, text

# UPDATE THIS WITH YOUR PASSWORD
DB_URL = "postgresql://postgres:Waheguru@localhost:5432/energy_pipeline"


def load_oil_data(df: pd.DataFrame) -> None:
    """
    Load cleaned oil production data into PostgreSQL.
    Uses bulk insert for performance.
    """

    print("Connecting to PostgreSQL...")

    engine = create_engine(DB_URL)

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