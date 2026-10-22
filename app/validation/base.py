"""Base classes and types for the Data Quality Validation Engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd


@dataclass
class ValidationFailure:
    """Represents a single data quality failure on a specific record."""

    source_entity: str
    record_identifier: Optional[str]
    raw_record_json: str
    rule_code: str
    rule_name: str
    error_message: str
    severity: str = "ERROR"  # 'ERROR' or 'WARNING'


class BaseRule(ABC):
    """Abstract base class for all data quality validation rules."""

    rule_code: str
    rule_name: str
    severity: str = "ERROR"

    @abstractmethod
    def validate(
        self,
        df: pd.DataFrame,
        raw_df: pd.DataFrame,
        entity_name: str,
        id_column: str,
        context: Optional[dict] = None,
    ) -> List[ValidationFailure]:
        """Execute validation rule on dataset.

        Args:
            df: Transformed/cleansed DataFrame being tested.
            raw_df: Original unadulterated DataFrame to preserve raw payload on failure.
            entity_name: Name of the entity ('sites', 'subjects', etc.)
            id_column: Name of the primary key / record identifier column.
            context: Optional dictionary containing external reference sets (e.g. parent PK sets).

        Returns:
            List of ValidationFailure objects for rows failing the rule.
        """
        pass
