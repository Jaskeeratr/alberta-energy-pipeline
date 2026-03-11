import pandas as pd


def transform_oil_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform Table S4.1 from the Alberta crude oil Excel workbook into a clean format.

    Output columns:
      - field_name
      - operator
      - production_date
      - volume_m3
    """
    print(f"Starting transform with {len(df):,} rows")

    df = df.copy()

    # Find the row that contains Table S4.1
    title_row_idx = None
    for i in range(len(df)):
        row_values = df.iloc[i].astype(str).tolist()
        row_text = " ".join(row_values)
        if "Table S4.1" in row_text:
            title_row_idx = i
            break

    if title_row_idx is None:
        raise ValueError("Could not find 'Table S4.1' in the workbook.")

    # In this workbook:
    # title row      -> title_row_idx
    # year row       -> title_row_idx + 1
    # unit row       -> title_row_idx + 2
    # data starts    -> title_row_idx + 3
    years_row_idx = title_row_idx + 1
    data_start_idx = title_row_idx + 3

    years_row = df.iloc[years_row_idx]

    # Find year columns (2023, 2024, 2025, ...)
    year_columns = []
    for col_idx, value in years_row.items():
        try:
            year = int(value)
            if 1900 <= year <= 2100:
                year_columns.append((col_idx, year))
        except (ValueError, TypeError):
            continue

    if not year_columns:
        raise ValueError("Could not find year columns in Table S4.1.")

    records = []

    # Read rows until we hit the next section
    for row_idx in range(data_start_idx, len(df)):
        label = df.iloc[row_idx, 0]

        if pd.isna(label):
            continue

        label = str(label).strip()

        # Stop when next section starts
        if label.lower().startswith("number of wells placed on production"):
            break

        # Clean the category label
        category = label.replace("\u2003", "").replace("\xa0", "").strip()
        if not category:
            continue

        for col_idx, year in year_columns:
            value = df.iloc[row_idx, col_idx]

            if pd.isna(value):
                continue

            value = pd.to_numeric(value, errors="coerce")
            if pd.isna(value):
                continue

            # Table S4.1 is reported as crude oil production (10^3 m3/d)
            # Multiply by 1000 so the stored number is closer to m3/d
            volume_m3 = float(value) * 1000

            records.append(
                {
                    "field_name": category.upper(),
                    "operator": "AER Summary",
                    "production_date": pd.to_datetime(f"{year}-01-01").date(),
                    "volume_m3": round(volume_m3, 2),
                }
            )

    clean_df = pd.DataFrame(records)

    if clean_df.empty:
        raise ValueError("Transform produced no rows.")

    # Final cleanup
    clean_df = clean_df.dropna(subset=["field_name", "production_date", "volume_m3"])
    clean_df = clean_df[clean_df["volume_m3"] >= 0]
    clean_df = clean_df.drop_duplicates()

    print(f"Transform complete: {len(clean_df):,} clean rows remaining")
    print("\nPreview of cleaned data:")
    print(clean_df.head())

    return clean_df