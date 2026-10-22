"""SQLAlchemy 2.0 ORM Declarative Models for the Clinical Trial Data Platform."""

from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


class DimSite(Base):
    """Clinical Trial Study Sites Dimension."""

    __tablename__ = "dim_sites"

    site_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    investigator_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    activation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    subjects: Mapped[list["DimSubject"]] = relationship("DimSubject", back_populates="site")


class DimSubject(Base):
    """Clinical Trial Subjects (Patients) Dimension."""

    __tablename__ = "dim_subjects"

    subject_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(50), ForeignKey("dim_sites.site_id"), nullable=False, index=True)
    enrollment_date: Mapped[date] = mapped_column(Date, nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENROLLED")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    site: Mapped["DimSite"] = relationship("DimSite", back_populates="subjects")
    visits: Mapped[list["FactVisit"]] = relationship("FactVisit", back_populates="subject")
    lab_results: Mapped[list["FactLabResult"]] = relationship("FactLabResult", back_populates="subject")


class FactVisit(Base):
    """Clinical Trial Subject Visit Events Fact Table."""

    __tablename__ = "fact_visits"

    visit_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("dim_subjects.subject_id"), nullable=False, index=True
    )
    visit_name: Mapped[str] = mapped_column(String(100), nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    visit_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ATTENDED")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    subject: Mapped["DimSubject"] = relationship("DimSubject", back_populates="visits")
    lab_results: Mapped[list["FactLabResult"]] = relationship("FactLabResult", back_populates="visit")


class FactLabResult(Base):
    """Clinical Laboratory Measurement Results Fact Table."""

    __tablename__ = "fact_lab_results"

    result_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    visit_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("fact_visits.visit_id"), nullable=False, index=True
    )
    subject_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("dim_subjects.subject_id"), nullable=False, index=True
    )
    test_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    test_name: Mapped[str] = mapped_column(String(150), nullable=False)
    result_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    collection_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    abnormal_flag: Mapped[str] = mapped_column(String(20), nullable=False, default="NORMAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    visit: Mapped["FactVisit"] = relationship("FactVisit", back_populates="lab_results")
    subject: Mapped["DimSubject"] = relationship("DimSubject", back_populates="lab_results")


class QuarantineRecord(Base):
    """Store for all records failing data quality checks during ETL."""

    __tablename__ = "quarantine_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("etl_pipeline_runs.run_id"), nullable=False, index=True
    )
    source_entity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    record_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    raw_record: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded raw string
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="ERROR")
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    run: Mapped["EtlPipelineRun"] = relationship("EtlPipelineRun", back_populates="quarantine_records")


class EtlPipelineRun(Base):
    """Metadata and execution metrics for every ETL pipeline execution."""

    __tablename__ = "etl_pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="STARTED")
    records_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_quarantined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_time_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    quarantine_records: Mapped[list["QuarantineRecord"]] = relationship(
        "QuarantineRecord", back_populates="run", cascade="all, delete-orphan"
    )
