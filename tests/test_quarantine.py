"""Unit tests for the Quarantine persistence layer."""

from app.validation.base import ValidationFailure
from app.validation.quarantine import build_quarantine_records, summarize_failures


def test_build_quarantine_records():
    """Verify conversion of ValidationFailure to QuarantineRecord ORM model."""
    failures = [
        ValidationFailure(
            source_entity="subjects",
            record_identifier="SUBJ-8888",
            raw_record_json='{"subject_id": "SUBJ-8888", "site_id": "SITE-999"}',
            rule_code="ERR_ORPHAN_FK",
            rule_name="Referential Integrity",
            error_message="Site does not exist.",
            severity="ERROR",
        ),
        # Duplicate failure to verify deduplication
        ValidationFailure(
            source_entity="subjects",
            record_identifier="SUBJ-8888",
            raw_record_json='{"subject_id": "SUBJ-8888", "site_id": "SITE-999"}',
            rule_code="ERR_ORPHAN_FK",
            rule_name="Referential Integrity",
            error_message="Site does not exist.",
            severity="ERROR",
        ),
    ]

    records = build_quarantine_records("test-run-123", failures)
    assert len(records) == 1
    assert records[0].run_id == "test-run-123"
    assert records[0].source_entity == "subjects"
    assert records[0].record_identifier == "SUBJ-8888"


def test_summarize_failures():
    """Verify statistical summarization of failures by rule and entity."""
    failures = [
        ValidationFailure("subjects", "S1", "{}", "ERR_ORPHAN_FK", "Ref Int", "Error 1"),
        ValidationFailure("subjects", "S2", "{}", "ERR_DUPLICATE_PK", "PK Uniq", "Error 2"),
        ValidationFailure("visits", "V1", "{}", "ERR_ORPHAN_FK", "Ref Int", "Error 3"),
    ]

    summary = summarize_failures(failures)
    assert summary["total_failures"] == 3
    assert summary["by_entity"]["subjects"] == 2
    assert summary["by_entity"]["visits"] == 1
    assert summary["by_rule"]["ERR_ORPHAN_FK"] == 2
    assert summary["by_rule"]["ERR_DUPLICATE_PK"] == 1
