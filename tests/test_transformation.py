"""Unit tests for the Transformation and cleansing stage."""

from datetime import date
import pandas as pd

from app.pipeline.transform import (
    clean_string_series,
    parse_date_series,
    parse_float_series,
    transform_lab_results,
    transform_sites,
    transform_subjects,
    transform_visits,
)


def test_clean_string_series():
    """Verify whitespace stripping and null equivalent mapping."""
    raw = pd.Series(["  active  ", "NA", "null", "None", "", "valid text"])
    cleaned = clean_string_series(raw)
    assert cleaned.iloc[0] == "active"
    assert pd.isna(cleaned.iloc[1])
    assert pd.isna(cleaned.iloc[2])
    assert pd.isna(cleaned.iloc[3])
    assert pd.isna(cleaned.iloc[4])
    assert cleaned.iloc[5] == "valid text"


def test_parse_date_series():
    """Verify date parsing and invalid date conversion to NaT."""
    raw = pd.Series(["2023-01-15", "invalid-date", "2023-02-31", None])
    dates = parse_date_series(raw)
    assert dates.iloc[0] == date(2023, 1, 15)
    assert pd.isna(dates.iloc[1])
    assert pd.isna(dates.iloc[2])
    assert pd.isna(dates.iloc[3])


def test_parse_float_series():
    """Verify numeric parsing and non-numeric coercion to NaN."""
    raw = pd.Series(["12.5", "-4.2", "not_a_number", ""])
    nums = parse_float_series(raw)
    assert nums.iloc[0] == 12.5
    assert nums.iloc[1] == -4.2
    assert pd.isna(nums.iloc[2])
    assert pd.isna(nums.iloc[3])


def test_transform_sites():
    """Verify sites standardization."""
    raw_df = pd.DataFrame([{
        "site_id": " SITE-101 ",
        "site_name": "  Clinic A ",
        "country": "usa",
        "status": "active",
        "activation_date": "2023-05-10",
    }])
    transformed = transform_sites(raw_df)
    assert transformed.loc[0, "site_id"] == "SITE-101"
    assert transformed.loc[0, "status"] == "ACTIVE"
    assert transformed.loc[0, "activation_date"] == date(2023, 5, 10)


def test_transform_lab_results():
    """Verify lab results numeric and date conversions."""
    raw_df = pd.DataFrame([{
        "result_id": "LAB-1",
        "visit_id": "VIS-1",
        "subject_id": "SUBJ-1",
        "test_code": "gluc",
        "test_name": "Glucose",
        "result_value": "95.5",
        "unit": "mg/dL",
        "collection_date": "2023-06-01",
        "abnormal_flag": "normal",
    }])
    transformed = transform_lab_results(raw_df)
    assert transformed.loc[0, "test_code"] == "GLUC"
    assert transformed.loc[0, "result_value"] == 95.5
    assert transformed.loc[0, "abnormal_flag"] == "NORMAL"
    assert transformed.loc[0, "collection_date"] == date(2023, 6, 1)
