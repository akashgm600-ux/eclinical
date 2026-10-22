"""Concrete Data Quality Rules for Clinical Trial Validation."""

import json
from typing import Any, List, Optional, Set
import pandas as pd

from app.validation.base import BaseRule, ValidationFailure


def row_to_json(raw_df: pd.DataFrame, idx: Any) -> str:
    """Safely convert a raw row to serialized JSON string."""
    try:
        row_dict = raw_df.loc[idx].to_dict()
        # Convert any timestamps or non-serializable objects
        clean_dict = {
            k: (str(v) if pd.notna(v) and not isinstance(v, (str, int, float, bool)) else v)
            for k, v in row_dict.items()
        }
        return json.dumps(clean_dict, default=str)
    except Exception:
        return "{}"


class RequiredFieldsRule(BaseRule):
    """Fails if any mandatory fields are null or empty."""

    rule_code = "ERR_REQUIRED_FIELD_MISSING"
    rule_name = "Mandatory Fields Completeness"

    def __init__(self, required_columns: List[str]):
        self.required_columns = required_columns

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        for idx, row in df.iterrows():
            missing = [col for col in self.required_columns if pd.isna(row.get(col))]
            if missing:
                raw_json = row_to_json(raw_df, idx)
                ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                failures.append(
                    ValidationFailure(
                        source_entity=entity_name,
                        record_identifier=ident,
                        raw_record_json=raw_json,
                        rule_code=self.rule_code,
                        rule_name=self.rule_name,
                        error_message=f"Mandatory column(s) missing or null: {', '.join(missing)}",
                        severity=self.severity,
                    )
                )
        return failures


class PrimaryKeyUniquenessRule(BaseRule):
    """Fails if duplicate identifiers exist within the dataset."""

    rule_code = "ERR_DUPLICATE_PK"
    rule_name = "Primary Key Uniqueness"

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        if id_column not in df.columns:
            return failures

        # Find duplicated values (excluding nulls, which are caught by RequiredFieldsRule)
        valid_ids = df[df[id_column].notna()]
        duplicated_mask = valid_ids.duplicated(subset=[id_column], keep="first")
        duplicate_indices = valid_ids[duplicated_mask].index

        for idx in duplicate_indices:
            raw_json = row_to_json(raw_df, idx)
            ident = str(df.loc[idx, id_column])
            failures.append(
                ValidationFailure(
                    source_entity=entity_name,
                    record_identifier=ident,
                    raw_record_json=raw_json,
                    rule_code=self.rule_code,
                    rule_name=self.rule_name,
                    error_message=f"Duplicate primary key '{ident}' detected in {entity_name}.",
                    severity=self.severity,
                )
            )
        return failures


class AllowedValuesRule(BaseRule):
    """Fails if a categorical column value is not in the allowed domain."""

    rule_code = "ERR_INVALID_ALLOWED_VALUE"
    rule_name = "Domain Categorical Conformance"

    def __init__(self, column: str, allowed_values: Set[str]):
        self.column = column
        self.allowed_values = allowed_values

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        if self.column not in df.columns:
            return failures

        for idx, row in df.iterrows():
            val = row.get(self.column)
            if pd.notna(val) and val not in self.allowed_values:
                raw_json = row_to_json(raw_df, idx)
                ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                failures.append(
                    ValidationFailure(
                        source_entity=entity_name,
                        record_identifier=ident,
                        raw_record_json=raw_json,
                        rule_code=self.rule_code,
                        rule_name=self.rule_name,
                        error_message=(
                            f"Value '{val}' in column '{self.column}' is not allowed. "
                            f"Expected one of: {sorted(list(self.allowed_values))}"
                        ),
                        severity=self.severity,
                    )
                )
        return failures


class DateFormatRule(BaseRule):
    """Fails if a date field failed parsing (is NaT) but had a non-empty raw string."""

    rule_code = "ERR_INVALID_DATE_FORMAT"
    rule_name = "ISO-8601 Date Validity"

    def __init__(self, date_columns: List[str]):
        self.date_columns = date_columns

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        for idx, row in df.iterrows():
            for d_col in self.date_columns:
                if d_col in df.columns:
                    raw_val = raw_df.loc[idx].get(d_col)
                    # If raw had a value, but parsed is NaT/None, format was invalid
                    if pd.notna(raw_val) and str(raw_val).strip() != "" and pd.isna(row.get(d_col)):
                        raw_json = row_to_json(raw_df, idx)
                        ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                        failures.append(
                            ValidationFailure(
                                source_entity=entity_name,
                                record_identifier=ident,
                                raw_record_json=raw_json,
                                rule_code=self.rule_code,
                                rule_name=self.rule_name,
                                error_message=f"Date '{raw_val}' in column '{d_col}' could not be parsed as valid ISO-8601 date.",
                                severity=self.severity,
                            )
                        )
                        break
        return failures


class ReferentialIntegrityRule(BaseRule):
    """Fails if a foreign key value does not exist in the allowed parent PK set."""

    rule_code = "ERR_ORPHAN_FK"
    rule_name = "Referential Integrity"

    def __init__(self, foreign_key_col: str, parent_entity: str, context_key: str):
        self.foreign_key_col = foreign_key_col
        self.parent_entity = parent_entity
        self.context_key = context_key

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        if context is None or self.context_key not in context:
            return failures

        valid_parent_keys: Set[str] = set(context[self.context_key])
        if self.foreign_key_col not in df.columns:
            return failures

        for idx, row in df.iterrows():
            fk_val = row.get(self.foreign_key_col)
            if pd.notna(fk_val) and fk_val not in valid_parent_keys:
                raw_json = row_to_json(raw_df, idx)
                ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                failures.append(
                    ValidationFailure(
                        source_entity=entity_name,
                        record_identifier=ident,
                        raw_record_json=raw_json,
                        rule_code=self.rule_code,
                        rule_name=self.rule_name,
                        error_message=(
                            f"Foreign key {self.foreign_key_col}='{fk_val}' does not exist in {self.parent_entity}."
                        ),
                        severity=self.severity,
                    )
                )
        return failures


class TemporalSequenceRule(BaseRule):
    """Fails if visit date is strictly earlier than the subject's enrollment date."""

    rule_code = "ERR_TEMPORAL_SEQUENCE"
    rule_name = "Clinical Chronology Sequence"

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        if context is None or "subject_enrollment_map" not in context:
            return failures

        subject_enrollment_map = context["subject_enrollment_map"]  # Dict[subject_id -> date]

        for idx, row in df.iterrows():
            subj_id = row.get("subject_id")
            vis_date = row.get("visit_date")
            if pd.notna(subj_id) and pd.notna(vis_date) and subj_id in subject_enrollment_map:
                enr_date = subject_enrollment_map[subj_id]
                if enr_date and vis_date < enr_date:
                    raw_json = row_to_json(raw_df, idx)
                    ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                    failures.append(
                        ValidationFailure(
                            source_entity=entity_name,
                            record_identifier=ident,
                            raw_record_json=raw_json,
                            rule_code=self.rule_code,
                            rule_name=self.rule_name,
                            error_message=(
                                f"Visit date {vis_date} occurs before subject enrollment date {enr_date}."
                            ),
                            severity=self.severity,
                        )
                    )
        return failures


class PhysiologicalBoundsRule(BaseRule):
    """Fails if lab results are biologically impossible (<= 0 or extreme outlier > 5000)."""

    rule_code = "ERR_PHYSIOLOGICAL_BOUNDS"
    rule_name = "Lab Physiological Plausibility"

    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        failures = []
        if "result_value" not in df.columns:
            return failures

        for idx, row in df.iterrows():
            val = row.get("result_value")
            test = row.get("test_code")
            if pd.notna(val):
                if val <= 0.0:
                    raw_json = row_to_json(raw_df, idx)
                    ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                    failures.append(
                        ValidationFailure(
                            source_entity=entity_name,
                            record_identifier=ident,
                            raw_record_json=raw_json,
                            rule_code=self.rule_code,
                            rule_name=self.rule_name,
                            error_message=f"Negative or zero lab value ({val}) for test {test} is biologically impossible.",
                            severity=self.severity,
                        )
                    )
                elif val > 5000.0:
                    raw_json = row_to_json(raw_df, idx)
                    ident = str(row.get(id_column)) if pd.notna(row.get(id_column)) else f"ROW_{idx}"
                    failures.append(
                        ValidationFailure(
                            source_entity=entity_name,
                            record_identifier=ident,
                            raw_record_json=raw_json,
                            rule_code=self.rule_code,
                            rule_name=self.rule_name,
                            error_message=f"Lab value ({val}) for test {test} exceeds maximum plausible limit (5000.0).",
                            severity=self.severity,
                        )
                    )
        return failures
