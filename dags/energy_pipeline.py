from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.extract import extract_oil_data
from scripts.transform import transform_oil_data
from scripts.load import (
    create_pipeline_run,
    finish_pipeline_run,
    load_data_quality_issues,
    load_oil_data,
)
from scripts.validate import validate_production_data


default_args = {
    "owner": "jaskeerat",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def run_pipeline():
    source_name = "crude_oil"
    run_id = create_pipeline_run(source_name)
    summary = {
        "rows_extracted": 0,
        "rows_valid": 0,
        "rows_rejected": 0,
        "error_rate": 0.0,
    }

    try:
        raw_df = extract_oil_data("/opt/airflow/data/raw/crude_oil_production.xlsx")
        clean_df = transform_oil_data(raw_df)
        valid_df, rejected_df, summary = validate_production_data(
            clean_df,
            source_name=source_name,
        )
        print("Validation summary:", summary)
        if not rejected_df.empty:
            print("Rejected rows preview:")
            print(rejected_df.head())
        load_data_quality_issues(run_id, source_name, rejected_df)
        load_oil_data(valid_df)
        finish_pipeline_run(
            run_id,
            status="success",
            rows_extracted=summary["rows_extracted"],
            rows_loaded=len(valid_df),
            rows_rejected=summary["rows_rejected"],
            error_rate=summary["error_rate"],
        )
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            rows_extracted=summary["rows_extracted"],
            rows_loaded=summary["rows_valid"],
            rows_rejected=summary["rows_rejected"],
            error_rate=summary["error_rate"],
            error_message=str(exc),
        )
        raise


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
