from scripts.extract import extract_oil_data
from scripts.transform import transform_oil_data
from scripts.load import (
    create_pipeline_run,
    finish_pipeline_run,
    load_data_quality_issues,
    load_oil_data,
)
from scripts.validate import validate_production_data


def main():
    source_name = "crude_oil"
    run_id = create_pipeline_run(source_name)
    summary = {
        "rows_extracted": 0,
        "rows_valid": 0,
        "rows_rejected": 0,
        "error_rate": 0.0,
    }

    try:
        # Extract
        raw_df = extract_oil_data("data/raw/crude_oil_production.xlsx")

        # Transform
        clean_df = transform_oil_data(raw_df)

        # Validate
        valid_df, rejected_df, summary = validate_production_data(
            clean_df,
            source_name=source_name,
        )
        print("\nValidation summary:")
        print(summary)
        if not rejected_df.empty:
            print("\nRejected rows preview:")
            print(rejected_df.head())

        # Audit and load
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

        print("\nPipeline run complete.")
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


if __name__ == "__main__":
    main()
