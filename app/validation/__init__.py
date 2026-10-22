"""Data Quality Validation Engine and Rules."""

from app.validation.base import BaseRule, ValidationFailure
from app.validation.engine import run_validation_pipeline, validate_entity
from app.validation.quarantine import build_quarantine_records, summarize_failures
from app.validation.rules import (
    AllowedValuesRule,
    DateFormatRule,
    PhysiologicalBoundsRule,
    PrimaryKeyUniquenessRule,
    ReferentialIntegrityRule,
    RequiredFieldsRule,
    TemporalSequenceRule,
)

__all__ = [
    "BaseRule",
    "ValidationFailure",
    "run_validation_pipeline",
    "validate_entity",
    "build_quarantine_records",
    "summarize_failures",
    "RequiredFieldsRule",
    "PrimaryKeyUniquenessRule",
    "AllowedValuesRule",
    "DateFormatRule",
    "ReferentialIntegrityRule",
    "TemporalSequenceRule",
    "PhysiologicalBoundsRule",
]
