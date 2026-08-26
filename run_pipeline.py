import argparse

from scripts.download import download_source_data
from scripts.extract import extract_gas_data, extract_oil_data
from scripts.transform import transform_gas_data, transform_oil_data
from scripts.load import (
    create_pipeline_run,
    finish_pipeline_run,
    load_data_quality_issues,
    load_gas_data,
    load_oil_data,
)
from scripts.validate import validate_production_data


SOURCES = {
    "crude_oil": {
        "filepath": "data/raw/crude_oil_production.xlsx",
        "extract_func": extract_oil_data,
        "transform_func": transform_oil_data,
        "load_func": load_oil_data,
    },
    "natural_gas": {
        "filepath": "data/raw/natural_gas_production.xlsx",
        "extract_func": extract_gas_data,
        "transform_func": transform_gas_data,
        "load_func": load_gas_data,
    },
}


def run_source_pipeline(
    source_name,
    filepath,
    extract_func,
    transform_func,
    load_func,
):
    run_id = create_pipeline_run(source_name)
    summary = {
        "rows_extracted": 0,
        "rows_valid": 0,
        "rows_rejected": 0,
        "error_rate": 0.0,
    }

    try:
        raw_df = extract_func(filepath)
        summary["rows_extracted"] = len(raw_df)

        clean_df = transform_func(raw_df)

        valid_df, rejected_df, summary = validate_production_data(
            clean_df,
            source_name=source_name,
        )
        print("\nValidation summary:")
        print(summary)
        if not rejected_df.empty:
            print("\nRejected rows preview:")
            print(rejected_df.head())

        load_data_quality_issues(run_id, source_name, rejected_df)
        load_func(valid_df)
        finish_pipeline_run(
            run_id,
            status="success",
            rows_extracted=summary["rows_extracted"],
            rows_loaded=len(valid_df),
            rows_rejected=summary["rows_rejected"],
            error_rate=summary["error_rate"],
        )

        print(f"\n{source_name} pipeline run complete.")
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the Alberta energy ETL pipeline.",
    )
    parser.add_argument(
        "--source",
        choices=[*SOURCES, "all"],
        default="all",
        help="Which source to run (default: all).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the latest AER workbooks before running the ETL.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.download:
        download_source_data()

    source_names = list(SOURCES) if args.source == "all" else [args.source]

    for source_name in source_names:
        run_source_pipeline(source_name, **SOURCES[source_name])

    print("\nAll pipeline runs complete.")


if __name__ == "__main__":
    main()
