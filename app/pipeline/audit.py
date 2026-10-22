"""Audit and operational logging for ETL pipeline executions."""

from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import EtlPipelineRun


def setup_logger(log_level: Optional[str] = None) -> logging.Logger:
    """Configure structured logging to console and rotating file."""
    level_name = (log_level or settings.LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("clinical_etl")
    logger.setLevel(level)

    # Avoid duplicate handlers on re-entry
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | [%(name)s:%(lineno)d] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

        # Rotating File handler
        log_file = settings.LOGS_DIR / "pipeline.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB per file
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger


def start_pipeline_run(
    session: Session,
    pipeline_name: Optional[str] = None,
    pipeline_version: Optional[str] = None,
) -> EtlPipelineRun:
    """Create an initial audit record for a new pipeline execution."""
    run_id = str(uuid.uuid4())
    run_record = EtlPipelineRun(
        run_id=run_id,
        pipeline_name=pipeline_name or settings.PIPELINE_NAME,
        pipeline_version=pipeline_version or settings.PIPELINE_VERSION,
        start_time=datetime.now(),
        status="STARTED",
        records_extracted=0,
        records_loaded=0,
        records_quarantined=0,
        execution_time_seconds=0.0,
    )
    session.add(run_record)
    session.flush()
    return run_record


def finish_pipeline_run(
    session: Session,
    run_record: EtlPipelineRun,
    records_extracted: int,
    records_loaded: int,
    records_quarantined: int,
    error_summary: Optional[str] = None,
) -> EtlPipelineRun:
    """Finalize an audit record with execution timing, row metrics, and final status."""
    end_time = datetime.now()
    duration = (end_time - run_record.start_time).total_seconds()

    if error_summary:
        status = "FAILED"
    elif records_quarantined > 0:
        status = "PARTIAL_SUCCESS"
    else:
        status = "SUCCESS"

    run_record.end_time = end_time
    run_record.execution_time_seconds = round(duration, 3)
    run_record.records_extracted = records_extracted
    run_record.records_loaded = records_loaded
    run_record.records_quarantined = records_quarantined
    run_record.status = status
    run_record.error_summary = error_summary

    session.flush()
    return run_record
