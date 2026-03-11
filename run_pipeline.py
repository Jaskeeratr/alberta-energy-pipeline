from scripts.extract import extract_oil_data
from scripts.transform import transform_oil_data
from scripts.load import load_oil_data


def main():

    # Extract
    raw_df = extract_oil_data("data/raw/crude_oil_production.xlsx")

    # Transform
    clean_df = transform_oil_data(raw_df)

    # Load
    load_oil_data(clean_df)

    print("\nPipeline run complete.")


if __name__ == "__main__":
    main()