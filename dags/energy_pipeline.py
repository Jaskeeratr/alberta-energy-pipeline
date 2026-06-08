from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.extract import extract_oil_data
from scripts.transform import transform_oil_data
from scripts.load import load_oil_data
from scripts.validate import validate_production_data


default_args = {
    "owner": "jaskeerat",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def run_pipeline():
    raw_df = extract_oil_data("/opt/airflow/data/raw/crude_oil_production.xlsx")
    clean_df = transform_oil_data(raw_df)
    valid_df, rejected_df, summary = validate_production_data(
        clean_df,
        source_name="crude_oil",
    )
    print("Validation summary:", summary)
    if not rejected_df.empty:
        print("Rejected rows preview:")
        print(rejected_df.head())
    load_oil_data(valid_df)


with DAG(
    dag_id="alberta_energy_pipeline",
    default_args=default_args,
    description="ETL pipeline for Alberta crude oil production data",
    start_date=datetime(2026, 1, 1),
    schedule="@monthly",
    catchup=False,
    tags=["etl", "postgres", "alberta-energy"],
) as dag:
    run_etl = PythonOperator(
        task_id="run_etl_pipeline",
        python_callable=run_pipeline,
    )
