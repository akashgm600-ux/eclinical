"""Validation Engine: Executes multi-tiered validation rules across entities."""

import logging
from typing import Dict, List, Tuple
import pandas as pd

from app.validation.base import ValidationFailure
from app.validation.rules import (
    AllowedValuesRule,
    DateFormatRule,
    PhysiologicalBoundsRule,
    PrimaryKeyUniquenessRule,
    ReferentialIntegrityRule,
    RequiredFieldsRule,
    TemporalSequenceRule,
)

logger = logging.getLogger(__name__)


def validate_entity(
    df: pd.DataFrame,
    raw_df: pd.DataFrame,
    entity_name: str,
    id_column: str,
    rules: list,
    context: dict = None,
) -> Tuple[pd.DataFrame, List[ValidationFailure]]:
    """Run a sequence of rules against an entity and partition into clean vs failed."""
    entity_failures: List[ValidationFailure] = []
    failed_indices = set()

    for rule in rules:
        failures = rule.validate(
            df=df,
            raw_df=raw_df,
            entity_name=entity_name,
            id_column=id_column,
            context=context or {},
        )
        if failures:
            entity_failures.extend(failures)
            # Find row indices of failed records
            for f in failures:
                # If record_identifier matches a row in df, mark its index
                if f.record_identifier and id_column in df.columns:
                    matched = df[df[id_column] == f.record_identifier].index.tolist()
                    failed_indices.update(matched)
                elif f.record_identifier and f.record_identifier.startswith("ROW_"):
                    try:
                        row_idx = int(f.record_identifier.split("_")[1])
                        failed_indices.add(row_idx)
                    except (ValueError, IndexError):
                        pass

    # Clean records are those not in failed_indices
    clean_df = df.drop(index=list(failed_indices)).copy().reset_index(drop=True)
    logger.info(
        f"Validation for '{entity_name}': {len(clean_df)} clean, {len(entity_failures)} failure issues across {len(failed_indices)} distinct rows."
    )
    return clean_df, entity_failures


def run_validation_pipeline(
    raw_datasets: Dict[str, pd.DataFrame],
    transformed_datasets: Dict[str, pd.DataFrame],
) -> Tuple[Dict[str, pd.DataFrame], List[ValidationFailure], dict]:
    """Execute complete hierarchical validation across Sites, Subjects, Visits, and Labs.

    Returns:
        Tuple of (clean_datasets, all_failures, quality_metrics)
    """
    logger.info("Initiating clinical trial data quality validation suite...")
    all_failures: List[ValidationFailure] = []
    clean_datasets: Dict[str, pd.DataFrame] = {}

    # -------------------------------------------------------------------------
    # 1. Validate Sites
    # -------------------------------------------------------------------------
    sites_rules = [
        RequiredFieldsRule(["site_id", "site_name", "country", "status"]),
        PrimaryKeyUniquenessRule(),
        AllowedValuesRule("status", {"ACTIVE", "CLOSED", "SUSPENDED"}),
        DateFormatRule(["activation_date"]),
    ]
    clean_sites, sites_fails = validate_entity(
        df=transformed_datasets["sites"],
        raw_df=raw_datasets["sites"],
        entity_name="sites",
        id_column="site_id",
        rules=sites_rules,
    )
    clean_datasets["sites"] = clean_sites
    all_failures.extend(sites_fails)

    # -------------------------------------------------------------------------
    # 2. Validate Subjects (Dependent on clean Sites)
    # -------------------------------------------------------------------------
    valid_site_ids = set(clean_sites["site_id"].dropna())
    subjects_context = {"valid_site_ids": valid_site_ids}

    subjects_rules = [
        RequiredFieldsRule(["subject_id", "site_id", "enrollment_date", "status"]),
        PrimaryKeyUniquenessRule(),
        AllowedValuesRule("status", {"ENROLLED", "ACTIVE", "COMPLETED", "WITHDRAWN", "SCREEN_FAIL"}),
        AllowedValuesRule("gender", {"M", "F", "OTHER"}),
        DateFormatRule(["enrollment_date", "date_of_birth"]),
        ReferentialIntegrityRule("site_id", "dim_sites", "valid_site_ids"),
    ]
    clean_subjects, subjects_fails = validate_entity(
        df=transformed_datasets["subjects"],
        raw_df=raw_datasets["subjects"],
        entity_name="subjects",
        id_column="subject_id",
        rules=subjects_rules,
        context=subjects_context,
    )
    clean_datasets["subjects"] = clean_subjects
    all_failures.extend(subjects_fails)

    # -------------------------------------------------------------------------
    # 3. Validate Visits (Dependent on clean Subjects)
    # -------------------------------------------------------------------------
    valid_subject_ids = set(clean_subjects["subject_id"].dropna())
    subject_enrollment_map = dict(
        zip(clean_subjects["subject_id"], clean_subjects["enrollment_date"])
    )
    visits_context = {
        "valid_subject_ids": valid_subject_ids,
        "subject_enrollment_map": subject_enrollment_map,
    }

    visits_rules = [
        RequiredFieldsRule(["visit_id", "subject_id", "visit_name", "visit_date", "visit_status"]),
        PrimaryKeyUniquenessRule(),
        AllowedValuesRule("visit_status", {"ATTENDED", "MISSED", "CANCELLED", "SCHEDULED"}),
        DateFormatRule(["visit_date"]),
        ReferentialIntegrityRule("subject_id", "dim_subjects", "valid_subject_ids"),
        TemporalSequenceRule(),
    ]
    clean_visits, visits_fails = validate_entity(
        df=transformed_datasets["visits"],
        raw_df=raw_datasets["visits"],
        entity_name="visits",
        id_column="visit_id",
        rules=visits_rules,
        context=visits_context,
    )
    clean_datasets["visits"] = clean_visits
    all_failures.extend(visits_fails)

    # -------------------------------------------------------------------------
    # 4. Validate Lab Results (Dependent on clean Visits and Subjects)
    # -------------------------------------------------------------------------
    valid_visit_ids = set(clean_visits["visit_id"].dropna())
    labs_context = {
        "valid_visit_ids": valid_visit_ids,
        "valid_subject_ids": valid_subject_ids,
    }

    labs_rules = [
        RequiredFieldsRule([
            "result_id", "visit_id", "subject_id", "test_code", "test_name",
            "result_value", "unit", "collection_date"
        ]),
        PrimaryKeyUniquenessRule(),
        DateFormatRule(["collection_date"]),
        ReferentialIntegrityRule("visit_id", "fact_visits", "valid_visit_ids"),
        ReferentialIntegrityRule("subject_id", "dim_subjects", "valid_subject_ids"),
        PhysiologicalBoundsRule(),
    ]
    clean_labs, labs_fails = validate_entity(
        df=transformed_datasets["lab_results"],
        raw_df=raw_datasets["lab_results"],
        entity_name="lab_results",
        id_column="result_id",
        rules=labs_rules,
        context=labs_context,
    )
    clean_datasets["lab_results"] = clean_labs
    all_failures.extend(labs_fails)

    # Quality metrics summary
    metrics = {
        "entities": {
            k: {
                "extracted": len(raw_datasets[k]),
                "clean": len(clean_datasets[k]),
                "rejected": len(raw_datasets[k]) - len(clean_datasets[k]),
            }
            for k in raw_datasets
        },
        "total_extracted": sum(len(raw_datasets[k]) for k in raw_datasets),
        "total_clean": sum(len(clean_datasets[k]) for k in clean_datasets),
        "total_failures": len(all_failures),
    }

    logger.info(
        f"Validation complete: Extracted={metrics['total_extracted']}, "
        f"Clean={metrics['total_clean']}, Failures={metrics['total_failures']}"
    )
    return clean_datasets, all_failures, metrics
