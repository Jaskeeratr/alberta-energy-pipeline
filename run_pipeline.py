import argparse

from scripts.download import download_source_data
from scripts.extract import extract_gas_data, extract_oil_data
from scripts.transform import transform_gas_data, transform_oil_data
from scripts.load import (
    create_pipeline_run,
    finish_pipeline_run,
    load_data_quality_issues,
    load_facility_production,
    load_gas_data,
    load_oil_data,
)
from scripts.petrinex import (
    download_month,
    extract_petrinex_data,
    transform_petrinex_data,
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


def run_petrinex_month(month, archive_path=None, data_dir="data/raw/petrinex"):
    """
    Run the Petrinex facility pipeline for one production month.

    Each month is tracked as its own audit run so a backfill produces one
    pipeline_runs record per month rather than one giant opaque run.
    """
    source_name = f"petrinex_{month}"
    run_id = create_pipeline_run(source_name)
    rows_extracted = 0

    try:
        if archive_path is None:
            archive_path = str(download_month(month, data_dir=data_dir))

        raw_df = extract_petrinex_data(archive_path)
        rows_extracted = len(raw_df)

        clean_df = transform_petrinex_data(raw_df)
        rows_loaded = load_facility_production(clean_df)

        # Rows dropped here are administrative records without a reported
        # volume, not validation failures.
        rows_skipped = rows_extracted - len(clean_df)
        finish_pipeline_run(
            run_id,
            status="success",
            rows_extracted=rows_extracted,
            rows_loaded=rows_loaded,
            rows_rejected=rows_skipped,
            error_rate=round(rows_skipped / rows_extracted, 4) if rows_extracted else 0.0,
        )
        print(f"\nPetrinex {month} complete: {rows_loaded:,} rows loaded.")
        return rows_loaded
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            rows_extracted=rows_extracted,
            error_message=str(exc),
        )
        raise


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the Alberta energy ETL pipeline.",
    )
    parser.add_argument(
        "--source",
        choices=[*SOURCES, "petrinex", "all"],
        default="all",
        help="Which source to run (default: all AER sources).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the latest AER workbooks before running the ETL.",
    )
    parser.add_argument(
        "--months",
        help=(
            "Comma-separated Petrinex production months to load, e.g. "
            "2026-01,2026-02,2026-03. Required with --source petrinex."
        ),
    )
    parser.add_argument(
        "--archive",
        help="Load a Petrinex month from an existing archive instead of downloading.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.source == "petrinex":
        if not args.months:
            raise SystemExit("--months is required with --source petrinex")
        months = [m.strip() for m in args.months.split(",") if m.strip()]
        total = 0
        for month in months:
            total += run_petrinex_month(month, archive_path=args.archive)
        print(f"\nPetrinex backfill complete: {total:,} rows across {len(months)} month(s).")
        return

    if args.download:
        download_source_data()

    source_names = list(SOURCES) if args.source == "all" else [args.source]

    for source_name in source_names:
        run_source_pipeline(source_name, **SOURCES[source_name])

    print("\nAll pipeline runs complete.")


if __name__ == "__main__":
    main()
