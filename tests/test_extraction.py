"""Unit tests for the Extraction stage."""

from pathlib import Path
import pytest
import pandas as pd

from app.pipeline.extract import (
    ExtractionError,
    calculate_file_hash,
    extract_datasets,
)


def test_calculate_file_hash(tmp_path: Path):
    """Verify SHA-256 computation on test file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Clinical Trial Data", encoding="utf-8")

    digest = calculate_file_hash(test_file)
    assert isinstance(digest, str)
    assert len(digest) == 64  # SHA-256 hex string length


def test_extract_datasets_success(tmp_path: Path):
    """Verify valid CSV extraction across all 4 clinical entities."""
    # Write minimum valid CSVs
    (tmp_path / "sites.csv").write_text("site_id,site_name,country,status\nSITE-1,Site 1,USA,ACTIVE", encoding="utf-8")
    (tmp_path / "subjects.csv").write_text("subject_id,site_id,enrollment_date,status\nSUBJ-1,SITE-1,2023-01-01,ENROLLED", encoding="utf-8")
    (tmp_path / "visits.csv").write_text("visit_id,subject_id,visit_name,visit_date,visit_status\nVIS-1,SUBJ-1,SCREEN,2023-01-02,ATTENDED", encoding="utf-8")
    (tmp_path / "lab_results.csv").write_text("result_id,visit_id,subject_id,test_code,test_name,result_value,unit,collection_date\nLAB-1,VIS-1,SUBJ-1,GLUC,Glucose,90.0,mg/dL,2023-01-02", encoding="utf-8")

    datasets, meta = extract_datasets(tmp_path)
    assert set(datasets.keys()) == {"sites", "subjects", "visits", "lab_results"}
    assert len(datasets["sites"]) == 1
    assert "sha256" in meta["sites"]


def test_extract_missing_directory():
    """Verify error raised when directory does not exist."""
    with pytest.raises(ExtractionError, match="Input directory does not exist"):
        extract_datasets("non_existent_directory_12345")


def test_extract_missing_required_file(tmp_path: Path):
    """Verify error raised when one of the CSV files is absent."""
    (tmp_path / "sites.csv").write_text("site_id,site_name,country,status\nSITE-1,Site 1,USA,ACTIVE")
    # Remaining 3 files missing
    with pytest.raises(ExtractionError, match="Required input file missing"):
        extract_datasets(tmp_path)


def test_extract_missing_mandatory_header(tmp_path: Path):
    """Verify error raised when CSV is missing required column."""
    # Missing 'country' column
    (tmp_path / "sites.csv").write_text("site_id,site_name,status\nSITE-1,Site 1,ACTIVE")
    (tmp_path / "subjects.csv").write_text("subject_id,site_id,enrollment_date,status\nSUBJ-1,SITE-1,2023-01-01,ENROLLED")
    (tmp_path / "visits.csv").write_text("visit_id,subject_id,visit_name,visit_date,visit_status\nVIS-1,SUBJ-1,SCREEN,2023-01-02,ATTENDED")
    (tmp_path / "lab_results.csv").write_text("result_id,visit_id,subject_id,test_code,test_name,result_value,unit,collection_date\nLAB-1,VIS-1,SUBJ-1,GLUC,Glucose,90.0,mg/dL,2023-01-02")

    with pytest.raises(ExtractionError, match="Missing required columns"):
        extract_datasets(tmp_path)
