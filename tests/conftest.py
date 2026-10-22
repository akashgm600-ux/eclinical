"""Pytest fixtures providing in-memory database and test client."""

import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.models import Base
from app.api.main import app


@pytest.fixture
def in_memory_engine():
    """Create isolated in-memory SQLite engine for tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(in_memory_engine):
    """Yield isolated SQLAlchemy session per test."""
    session_factory = sessionmaker(bind=in_memory_engine)
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_clean_sites():
    """Return clean sample Sites DataFrame."""
    return pd.DataFrame([
        {
            "site_id": "SITE-101",
            "site_name": "Test Site 1",
            "country": "USA",
            "investigator_name": "Dr. Smith",
            "activation_date": date(2023, 1, 1),
            "status": "ACTIVE",
        },
        {
            "site_id": "SITE-102",
            "site_name": "Test Site 2",
            "country": "Germany",
            "investigator_name": "Dr. Miller",
            "activation_date": date(2023, 2, 1),
            "status": "ACTIVE",
        },
    ])


@pytest.fixture
def sample_clean_subjects():
    """Return clean sample Subjects DataFrame."""
    return pd.DataFrame([
        {
            "subject_id": "SUBJ-1001",
            "site_id": "SITE-101",
            "enrollment_date": date(2023, 3, 1),
            "date_of_birth": date(1985, 5, 20),
            "gender": "M",
            "status": "ENROLLED",
        },
        {
            "subject_id": "SUBJ-1002",
            "site_id": "SITE-102",
            "enrollment_date": date(2023, 3, 15),
            "date_of_birth": date(1990, 8, 10),
            "gender": "F",
            "status": "ACTIVE",
        },
    ])
