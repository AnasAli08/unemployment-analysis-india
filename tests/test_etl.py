import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import etl  # noqa: E402


def test_area_file_has_no_nulls_or_blank_rows():
    df = etl.clean_area_file()
    assert df.isnull().sum().sum() == 0
    assert len(df) == 740            # 768 raw rows - 28 blank rows


def test_area_file_columns_are_standardised():
    df = etl.clean_area_file()
    expected = {"region", "date", "frequency", "unemployment_rate", "employed",
                "labour_participation", "area", "period"}
    assert set(df.columns) == expected


def test_dates_are_parsed_as_datetime():
    df = etl.clean_area_file()
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["date"].min() == pd.Timestamp("2019-05-31")
    assert df["date"].max() == pd.Timestamp("2020-06-30")


def test_period_labels():
    df = etl.clean_area_file()
    assert set(df.loc[df["date"] < "2020-03-01", "period"]) == {"pre_covid"}
    assert set(df.loc[df["date"].between("2020-04-01", "2020-05-31"), "period"]) == {"lockdown"}


def test_regional_file_coordinates_are_fixed():
    df = etl.clean_regional_file()
    ap = df[df["region"] == "Andhra Pradesh"].iloc[0]
    assert 12 < ap["latitude"] < 20          # raw file had latitude/longitude swapped
    assert 76 < ap["longitude"] < 82


def test_regional_file_frequency_is_standardised():
    df = etl.clean_regional_file()
    assert set(df["frequency"]) == {"Monthly"}
