"""
ETL: raw CSVs -> cleaned DataFrames -> SQLite database.

Run from the repo root:  python src/etl.py
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "unemployment.db"

AREA_FILE = RAW_DIR / "Unemployment in India.csv"              # May 2019 - Jun 2020, Rural/Urban split
REGIONAL_FILE = RAW_DIR / "Unemployment_Rate_upto_11_2020.csv"  # Jan 2020 - Oct 2020, macro-regions

LOCKDOWN_START = "2020-03-01"  # national lockdown began 25 Mar 2020; March is treated as a transition month

RENAME = {
    "Region": "region",
    "Date": "date",
    "Frequency": "frequency",
    "Estimated Unemployment Rate (%)": "unemployment_rate",
    "Estimated Employed": "employed",
    "Estimated Labour Participation Rate (%)": "labour_participation",
    "Area": "area",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("etl")


def add_period(df: pd.DataFrame) -> pd.DataFrame:
    """Label each row: pre_covid (before Mar 2020), lockdown (Apr-May 2020), transition (Mar, Jun+)."""
    df = df.copy()
    conditions = [
        df["date"] < pd.Timestamp(LOCKDOWN_START),
        df["date"].between("2020-04-01", "2020-05-31"),
    ]
    df["period"] = np.select(conditions, ["pre_covid", "lockdown"], default="transition")
    return df


def clean_area_file(path: Path = AREA_FILE) -> pd.DataFrame:
    """Clean 'Unemployment in India.csv' (state x Rural/Urban x month)."""
    df = pd.read_csv(path, encoding="utf-8-sig")        # utf-8-sig removes the hidden BOM before 'Region'
    df.columns = df.columns.str.strip()                  # headers have stray spaces
    n_raw = len(df)

    df = df.dropna(how="all")                            # file contains fully blank rows
    log.info("area file: dropped %d blank rows", n_raw - len(df))

    df = df.rename(columns=RENAME)
    for col in ["region", "frequency", "area"]:
        df[col] = df[col].str.strip()
    df["date"] = pd.to_datetime(df["date"].str.strip(), format="%d-%m-%Y")

    n_before = len(df)
    df = df.drop_duplicates()
    log.info("area file: dropped %d duplicate rows", n_before - len(df))

    df = add_period(df).sort_values(["region", "area", "date"]).reset_index(drop=True)
    return df


def clean_regional_file(path: Path = REGIONAL_FILE) -> pd.DataFrame:
    """Clean 'Unemployment_Rate_upto_11_2020.csv' (state x month, with macro-region and coordinates)."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    # The file has two columns named 'Region'; pandas renames the second one to 'Region.1' (North/South/...).
    df = df.rename(columns=RENAME).rename(columns={"Region.1": "macro_region"})

    # In the raw file 'longitude' holds latitude values (e.g. Andhra Pradesh: 15.91) and vice versa. Swap back.
    df = df.rename(columns={"longitude": "latitude", "latitude": "longitude"})

    df["region"] = df["region"].str.strip()
    df["macro_region"] = df["macro_region"].str.strip()
    df["frequency"] = df["frequency"].str.strip().replace({"M": "Monthly"})
    df["date"] = pd.to_datetime(df["date"].str.strip(), format="%d-%m-%Y")

    df = df.drop_duplicates()
    df = add_period(df).sort_values(["region", "date"]).reset_index(drop=True)
    return df


def validate(df: pd.DataFrame, name: str) -> None:
    """Fail loudly if the cleaned data breaks basic expectations."""
    assert df.isnull().sum().sum() == 0, f"{name}: null values remain"
    assert df["unemployment_rate"].between(0, 100).all(), f"{name}: unemployment_rate outside 0-100"
    assert (df["frequency"] == "Monthly").all(), f"{name}: unexpected frequency"
    log.info("%s: validation passed (%d rows)", name, len(df))


def load_to_sqlite(tables: dict, db_path: Path = DB_PATH) -> None:
    """Write each DataFrame to its own table (dates stored as ISO text, e.g. 2020-04-30)."""
    with sqlite3.connect(db_path) as conn:
        for name, df in tables.items():
            out = df.copy()
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")
            out.to_sql(name, conn, if_exists="replace", index=False)
            log.info("loaded table '%s' (%d rows) into %s", name, len(out), db_path.name)


def main() -> None:
    area = clean_area_file()
    regional = clean_regional_file()
    validate(area, "unemployment_area")
    validate(regional, "unemployment_regional_2020")
    load_to_sqlite({"unemployment_area": area, "unemployment_regional_2020": regional})


if __name__ == "__main__":
    main()
