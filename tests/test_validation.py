"""Unit tests for the Data Quality Validation Rules Engine."""

from datetime import date
import pandas as pd

from app.validation.rules import (
    AllowedValuesRule,
    DateFormatRule,
    PhysiologicalBoundsRule,
    PrimaryKeyUniquenessRule,
    ReferentialIntegrityRule,
    RequiredFieldsRule,
    TemporalSequenceRule,
)


def test_required_fields_rule():
    """Verify detection of missing mandatory fields."""
    rule = RequiredFieldsRule(["site_id", "site_name"])
    raw_df = pd.DataFrame([
        {"site_id": "SITE-1", "site_name": None},
        {"site_id": "SITE-2", "site_name": "Clinic B"},
    ])
    df = raw_df.copy()

    failures = rule.validate(df, raw_df, "sites", "site_id")
    assert len(failures) == 1
    assert failures[0].rule_code == "ERR_REQUIRED_FIELD_MISSING"
    assert "site_name" in failures[0].error_message


def test_primary_key_uniqueness_rule():
    """Verify duplicate primary key detection."""
    rule = PrimaryKeyUniquenessRule()
    raw_df = pd.DataFrame([
        {"site_id": "SITE-1", "site_name": "Clinic A"},
        {"site_id": "SITE-1", "site_name": "Clinic A Duplicate"},
    ])
    df = raw_df.copy()

    failures = rule.validate(df, raw_df, "sites", "site_id")
    assert len(failures) == 1
    assert failures[0].rule_code == "ERR_DUPLICATE_PK"
    assert "SITE-1" in failures[0].record_identifier


def test_allowed_values_rule():
    """Verify domain validation rejects unrecognized status."""
    rule = AllowedValuesRule("status", {"ACTIVE", "CLOSED"})
    raw_df = pd.DataFrame([
        {"site_id": "SITE-1", "status": "PENDING_APPROVAL"},
        {"site_id": "SITE-2", "status": "ACTIVE"},
    ])
    df = raw_df.copy()

    failures = rule.validate(df, raw_df, "sites", "site_id")
    assert len(failures) == 1
    assert failures[0].rule_code == "ERR_INVALID_ALLOWED_VALUE"
    assert "PENDING_APPROVAL" in failures[0].error_message


def test_date_format_rule():
    """Verify unparseable dates generate validation failure."""
    rule = DateFormatRule(["enrollment_date"])
    raw_df = pd.DataFrame([
        {"subject_id": "SUBJ-1", "enrollment_date": "31/02/2023"},
    ])
    df = pd.DataFrame([
        {"subject_id": "SUBJ-1", "enrollment_date": pd.NaT},
    ])

    failures = rule.validate(df, raw_df, "subjects", "subject_id")
    assert len(failures) == 1
    assert failures[0].rule_code == "ERR_INVALID_DATE_FORMAT"


def test_referential_integrity_rule():
    """Verify orphan foreign keys are identified."""
    rule = ReferentialIntegrityRule("site_id", "dim_sites", "valid_site_ids")
    raw_df = pd.DataFrame([
        {"subject_id": "SUBJ-1", "site_id": "SITE-999"},
        {"subject_id": "SUBJ-2", "site_id": "SITE-101"},
    ])
    df = raw_df.copy()
    context = {"valid_site_ids": {"SITE-101", "SITE-102"}}

    failures = rule.validate(df, raw_df, "subjects", "subject_id", context=context)
    assert len(failures) == 1
    assert failures[0].rule_code == "ERR_ORPHAN_FK"
    assert "SITE-999" in failures[0].error_message


def test_temporal_sequence_rule():
    """Verify chronological sequence check catches visit before enrollment."""
    rule = TemporalSequenceRule()
    raw_df = pd.DataFrame([
        {"visit_id": "VIS-1", "subject_id": "SUBJ-1", "visit_date": date(2023, 1, 10)},
    ])
    df = raw_df.copy()
    context = {"subject_enrollment_map": {"SUBJ-1": date(2023, 2, 1)}}

    failures = rule.validate(df, raw_df, "visits", "visit_id", context=context)
    assert len(failures) == 1
    assert failures[0].rule_code == "ERR_TEMPORAL_SEQUENCE"


def test_physiological_bounds_rule():
    """Verify negative and extreme lab values are flagged."""
    rule = PhysiologicalBoundsRule()
    raw_df = pd.DataFrame([
        {"result_id": "LAB-1", "test_code": "GLUC", "result_value": -15.0},
        {"result_id": "LAB-2", "test_code": "HGB", "result_value": 9999.0},
        {"result_id": "LAB-3", "test_code": "ALT", "result_value": 35.0},
    ])
    df = raw_df.copy()

    failures = rule.validate(df, raw_df, "lab_results", "result_id")
    assert len(failures) == 2
    codes = [f.rule_code for f in failures]
    assert all(c == "ERR_PHYSIOLOGICAL_BOUNDS" for c in codes)
