from scripts.extract import extract_oil_data
from scripts.transform import transform_oil_data
from scripts.load import load_oil_data
from scripts.validate import validate_production_data


def main():

    # Extract
    raw_df = extract_oil_data("data/raw/crude_oil_production.xlsx")

    # Transform
    clean_df = transform_oil_data(raw_df)

    # Validate
    valid_df, rejected_df, summary = validate_production_data(
        clean_df,
        source_name="crude_oil",
    )
    print("\nValidation summary:")
    print(summary)
    if not rejected_df.empty:
        print("\nRejected rows preview:")
        print(rejected_df.head())

    # Load
    load_oil_data(valid_df)

    print("\nPipeline run complete.")


if __name__ == "__main__":
    main()
