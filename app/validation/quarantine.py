"""Quarantine persistence and management layer."""

import logging
from typing import Dict, List
from app.database.models import QuarantineRecord
from app.validation.base import ValidationFailure

logger = logging.getLogger(__name__)


def build_quarantine_records(
    run_id: str, failures: List[ValidationFailure]
) -> List[QuarantineRecord]:
    """Convert ValidationFailure dataclass instances into QuarantineRecord ORM models."""
    records: List[QuarantineRecord] = []
    seen = set()

    for f in failures:
        # Prevent exact duplicate failure logging for same record and rule
        dedup_key = (f.source_entity, f.record_identifier, f.rule_code)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        records.append(
            QuarantineRecord(
                run_id=run_id,
                source_entity=f.source_entity,
                record_identifier=f.record_identifier,
                raw_record=f.raw_record_json,
                rule_code=f.rule_code,
                rule_name=f.rule_name,
                error_message=f.error_message,
                severity=f.severity,
            )
        )

    logger.info(f"Generated {len(records)} quarantine ORM records for run '{run_id}'")
    return records


def summarize_failures(failures: List[ValidationFailure]) -> Dict[str, dict]:
    """Produce summary statistics of validation failures by entity and rule."""
    summary = {
        "total_failures": len(failures),
        "by_entity": {},
        "by_rule": {},
        "by_severity": {},
    }

    for f in failures:
        # Entity tally
        summary["by_entity"][f.source_entity] = summary["by_entity"].get(f.source_entity, 0) + 1
        # Rule tally
        summary["by_rule"][f.rule_code] = summary["by_rule"].get(f.rule_code, 0) + 1
        # Severity tally
        summary["by_severity"][f.severity] = summary["by_severity"].get(f.severity, 0) + 1

    return summary
