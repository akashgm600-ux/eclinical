"""Transformation Stage: Cleanses, standardizes, and parses raw extracted datasets."""

import logging
from typing import Dict
import pandas as pd

logger = logging.getLogger(__name__)

NULL_EQUIVALENTS = {"", "na", "n/a", "null", "none", "nan"}


def clean_string_series(series: pd.Series) -> pd.Series:
    """Trim whitespace and convert string empty/null equivalents to None."""
    def _clean_val(v):
        if pd.isna(v):
            return None
        s = str(v).strip()
        if s.lower() in NULL_EQUIVALENTS:
            return None
        return s
    return series.apply(_clean_val)


def parse_date_series(series: pd.Series) -> pd.Series:
    """Parse dates to ISO-8601 date objects; invalid strings become NaT."""
    cleaned = clean_string_series(series)
    return pd.to_datetime(cleaned, format="ISO8601", errors="coerce").dt.date


def parse_float_series(series: pd.Series) -> pd.Series:
    """Convert string numbers to float, coercing invalid entries to NaN."""
    cleaned = clean_string_series(series)
    return pd.to_numeric(cleaned, errors="coerce")


def transform_sites(df: pd.DataFrame) -> pd.DataFrame:
    """Cleanse and standardize Sites dataset."""
    t_df = df.copy()
    t_df["site_id"] = clean_string_series(t_df["site_id"])
    t_df["site_name"] = clean_string_series(t_df["site_name"])
    t_df["country"] = clean_string_series(t_df["country"])
    if "investigator_name" in t_df.columns:
        t_df["investigator_name"] = clean_string_series(t_df["investigator_name"])

    # Standardize status
    t_df["status"] = clean_string_series(t_df["status"]).apply(
        lambda v: v.upper() if v else None
    )

    # Parse activation date
    if "activation_date" in t_df.columns:
        t_df["activation_date"] = parse_date_series(t_df["activation_date"])

    return t_df


def transform_subjects(df: pd.DataFrame) -> pd.DataFrame:
    """Cleanse and standardize Subjects dataset."""
    t_df = df.copy()
    t_df["subject_id"] = clean_string_series(t_df["subject_id"])
    t_df["site_id"] = clean_string_series(t_df["site_id"])

    # Standardize status and gender
    t_df["status"] = clean_string_series(t_df["status"]).apply(
        lambda v: v.upper() if v else None
    )
    if "gender" in t_df.columns:
        t_df["gender"] = clean_string_series(t_df["gender"]).apply(
            lambda v: v.upper() if v else None
        )

    t_df["enrollment_date"] = parse_date_series(t_df["enrollment_date"])
    if "date_of_birth" in t_df.columns:
        t_df["date_of_birth"] = parse_date_series(t_df["date_of_birth"])

    return t_df


def transform_visits(df: pd.DataFrame) -> pd.DataFrame:
    """Cleanse and standardize Protocol Visits dataset."""
    t_df = df.copy()
    t_df["visit_id"] = clean_string_series(t_df["visit_id"])
    t_df["subject_id"] = clean_string_series(t_df["subject_id"])
    t_df["visit_name"] = clean_string_series(t_df["visit_name"]).apply(
        lambda v: v.upper() if v else None
    )
    t_df["visit_status"] = clean_string_series(t_df["visit_status"]).apply(
        lambda v: v.upper() if v else None
    )
    t_df["visit_date"] = parse_date_series(t_df["visit_date"])

    return t_df


def transform_lab_results(df: pd.DataFrame) -> pd.DataFrame:
    """Cleanse and standardize Laboratory Results dataset."""
    t_df = df.copy()
    t_df["result_id"] = clean_string_series(t_df["result_id"])
    t_df["visit_id"] = clean_string_series(t_df["visit_id"])
    t_df["subject_id"] = clean_string_series(t_df["subject_id"])
    t_df["test_code"] = clean_string_series(t_df["test_code"]).apply(
        lambda v: v.upper() if v else None
    )
    t_df["test_name"] = clean_string_series(t_df["test_name"])
    t_df["unit"] = clean_string_series(t_df["unit"])

    t_df["result_value"] = parse_float_series(t_df["result_value"])
    if "reference_low" in t_df.columns:
        t_df["reference_low"] = parse_float_series(t_df["reference_low"])
    if "reference_high" in t_df.columns:
        t_df["reference_high"] = parse_float_series(t_df["reference_high"])

    t_df["collection_date"] = parse_date_series(t_df["collection_date"])

    if "abnormal_flag" in t_df.columns:
        t_df["abnormal_flag"] = clean_string_series(t_df["abnormal_flag"]).apply(
            lambda v: v.upper() if v else "NORMAL"
        )
    else:
        t_df["abnormal_flag"] = "NORMAL"

    return t_df


def transform_datasets(raw_datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Execute transformations for all extracted clinical datasets."""
    logger.info("Transforming extracted clinical datasets...")
    transformed = {
        "sites": transform_sites(raw_datasets["sites"]),
        "subjects": transform_subjects(raw_datasets["subjects"]),
        "visits": transform_visits(raw_datasets["visits"]),
        "lab_results": transform_lab_results(raw_datasets["lab_results"]),
    }
    logger.info("Completed transformation for all entities.")
    return transformed
