"""Unit tests for Database Loading, Idempotency, and Transaction Rollbacks."""

from datetime import date
import pandas as pd
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.models import DimSite, DimSubject, FactLabResult, FactVisit
from app.pipeline.load import load_clean_data, upsert_records


def test_upsert_records_idempotent(db_session: Session):
    """Verify upserting the exact same record twice updates instead of duplicating."""
    records_first_pass = [
        {"site_id": "SITE-101", "site_name": "Clinic Alpha", "country": "USA", "status": "ACTIVE"},
        {"site_id": "SITE-102", "site_name": "Clinic Beta", "country": "Germany", "status": "ACTIVE"},
    ]

    # First insert
    count1 = upsert_records(db_session, DimSite, records_first_pass, pk_column="site_id")
    db_session.commit()
    assert count1 == 2

    sites_in_db = db_session.execute(select(DimSite)).scalars().all()
    assert len(sites_in_db) == 2

    # Second pass with updated site_name
    records_second_pass = [
        {"site_id": "SITE-101", "site_name": "Clinic Alpha (Updated)", "country": "USA", "status": "ACTIVE"},
        {"site_id": "SITE-102", "site_name": "Clinic Beta", "country": "Germany", "status": "ACTIVE"},
    ]
    count2 = upsert_records(db_session, DimSite, records_second_pass, pk_column="site_id")
    db_session.commit()
    assert count2 == 2

    # Must still have only 2 records, but SITE-101 name is updated
    updated_sites = db_session.execute(select(DimSite)).scalars().all()
    assert len(updated_sites) == 2
    site_101 = db_session.get(DimSite, "SITE-101")
    assert site_101.site_name == "Clinic Alpha (Updated)"


def test_load_clean_data_complete(db_session: Session, sample_clean_sites, sample_clean_subjects):
    """Verify end-to-end loading across multiple related entities."""
    visits_df = pd.DataFrame([{
        "visit_id": "VIS-1",
        "subject_id": "SUBJ-1001",
        "visit_name": "SCREENING",
        "visit_date": date(2023, 3, 5),
        "visit_status": "ATTENDED",
    }])
    labs_df = pd.DataFrame([{
        "result_id": "LAB-1",
        "visit_id": "VIS-1",
        "subject_id": "SUBJ-1001",
        "test_code": "GLUC",
        "test_name": "Glucose",
        "result_value": 90.0,
        "unit": "mg/dL",
        "collection_date": date(2023, 3, 5),
        "abnormal_flag": "NORMAL",
    }])

    clean_datasets = {
        "sites": sample_clean_sites,
        "subjects": sample_clean_subjects,
        "visits": visits_df,
        "lab_results": labs_df,
    }

    counts = load_clean_data(db_session, clean_datasets, quarantine_records=[])
    db_session.commit()

    assert counts["dim_sites"] == 2
    assert counts["dim_subjects"] == 2
    assert counts["fact_visits"] == 1
    assert counts["fact_lab_results"] == 1


def test_transaction_rollback_on_failure(db_session: Session):
    """Verify that an exception rolls back uncommitted changes."""
    # Insert valid site
    db_session.add(DimSite(site_id="SITE-ORIGINAL", site_name="Original", country="USA", status="ACTIVE"))
    db_session.commit()

    try:
        # Begin nested failure attempt
        db_session.add(DimSite(site_id="SITE-FAIL", site_name="Fail", country="USA", status="ACTIVE"))
        # Force a database failure: invalid SQL
        db_session.execute(text("INSERT INTO non_existent_table VALUES (1)"))
        db_session.commit()
    except Exception:
        db_session.rollback()

    # Verify SITE-FAIL was NOT persisted due to rollback
    site = db_session.get(DimSite, "SITE-FAIL")
    assert site is None
    original_site = db_session.get(DimSite, "SITE-ORIGINAL")
    assert original_site is not None
