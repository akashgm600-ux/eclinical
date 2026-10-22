"""End-to-end integration tests for the full ETL pipeline execution."""

from pathlib import Path
from app.pipeline.runner import run_pipeline


def test_full_pipeline_e2e(tmp_path: Path):
    """Execute end-to-end pipeline run against an isolated SQLite test database."""
    # Create sample CSVs in temp directory
    (tmp_path / "sites.csv").write_text(
        "site_id,site_name,country,investigator_name,activation_date,status\n"
        "SITE-1,Alpha Center,USA,Dr. One,2023-01-01,ACTIVE\n"
        "SITE-2,Beta Clinic,Germany,Dr. Two,2023-01-15,ACTIVE\n"
        "SITE-1,Alpha Duplicate,USA,Dr. One,2023-01-01,ACTIVE\n",  # Duplicate PK
        encoding="utf-8",
    )
    (tmp_path / "subjects.csv").write_text(
        "subject_id,site_id,enrollment_date,date_of_birth,gender,status\n"
        "SUBJ-1,SITE-1,2023-02-01,1980-01-01,M,ENROLLED\n"        # Orphan due to quarantined SITE-1
        "SUBJ-2,SITE-2,2023-02-01,1985-05-05,F,ENROLLED\n"        # Clean subject under clean SITE-2
        "SUBJ-3,SITE-999,2023-02-01,1990-09-09,M,ENROLLED\n",     # Orphan Site FK
        encoding="utf-8",
    )
    (tmp_path / "visits.csv").write_text(
        "visit_id,subject_id,visit_name,visit_date,visit_status\n"
        "VIS-1,SUBJ-2,SCREENING,2023-02-10,ATTENDED\n"            # Clean visit
        "VIS-2,SUBJ-2,BASELINE,2023-01-01,ATTENDED\n",            # Chronological violation (before enrollment)
        encoding="utf-8",
    )
    (tmp_path / "lab_results.csv").write_text(
        "result_id,visit_id,subject_id,test_code,test_name,result_value,unit,collection_date,abnormal_flag\n"
        "LAB-1,VIS-1,SUBJ-2,GLUC,Glucose,85.0,mg/dL,2023-02-10,NORMAL\n"     # Clean lab
        "LAB-2,VIS-1,SUBJ-2,HGB,Hemoglobin,-12.0,g/dL,2023-02-10,CRITICAL\n", # Negative value failure
        encoding="utf-8",
    )

    db_path = tmp_path / "test_pipeline.db"
    db_url = f"sqlite:///{db_path}"

    summary = run_pipeline(input_dir=str(tmp_path), db_url=db_url)

    assert summary["status"] == "PARTIAL_SUCCESS"
    assert summary["records_extracted"] == 10
    assert summary["records_loaded"] == 4  # SITE-2, SUBJ-2, VIS-1, LAB-1
    assert summary["records_quarantined"] >= 5
    assert summary["data_quality_pass_rate_pct"] == 40.0
