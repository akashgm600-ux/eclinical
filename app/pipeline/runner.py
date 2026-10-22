"""Pipeline Orchestration Engine: Coordinates Extract, Transform, Validate, Load, and Audit."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db_session, get_engine, init_db
from app.database.models import EtlPipelineRun
from app.pipeline.audit import finish_pipeline_run, setup_logger, start_pipeline_run
from app.pipeline.extract import extract_datasets
from app.pipeline.load import load_clean_data
from app.pipeline.transform import transform_datasets
from app.validation.engine import run_validation_pipeline
from app.validation.quarantine import build_quarantine_records, summarize_failures

logger = setup_logger()


def run_pipeline(
    input_dir: Optional[Path | str] = None,
    db_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the end-to-end Clinical Trial ETL pipeline.

    Args:
        input_dir: Directory containing raw/sample CSV datasets.
        db_url: Optional database connection string override.

    Returns:
        Dict containing execution summary metrics, run_id, and status.
    """
    source_dir = Path(input_dir) if input_dir else settings.INPUT_DATA_DIR
    logger.info("=" * 80)
    logger.info(f"STARTING CLINICAL TRIAL ETL PIPELINE RUN [Input: {source_dir}]")
    logger.info("=" * 80)

    # Ensure tables exist
    engine = get_engine(db_url)
    init_db(engine)

    run_id = None
    with get_db_session(db_url) as session:
        try:
            # 1. Audit Start
            audit_run: EtlPipelineRun = start_pipeline_run(session)
            run_id = audit_run.run_id
            logger.info(f"Initialized Pipeline Run ID: {run_id}")

            # 2. Extract
            raw_datasets, file_meta = extract_datasets(source_dir)
            total_extracted = sum(len(df) for df in raw_datasets.values())
            logger.info(f"Extraction successful: {total_extracted} total rows extracted.")

            # 3. Transform
            transformed_datasets = transform_datasets(raw_datasets)

            # 4. Validate
            clean_datasets, failures, val_metrics = run_validation_pipeline(
                raw_datasets, transformed_datasets
            )

            # 5. Quarantine
            quarantine_records = build_quarantine_records(run_id, failures)
            quarantine_summary = summarize_failures(failures)

            # 6. Load (Clean records + Quarantine)
            loaded_counts = load_clean_data(
                session, clean_datasets, quarantine_records
            )
            total_clean_loaded = (
                loaded_counts.get("dim_sites", 0)
                + loaded_counts.get("dim_subjects", 0)
                + loaded_counts.get("fact_visits", 0)
                + loaded_counts.get("fact_lab_results", 0)
            )

            # 7. Audit Finish
            finish_pipeline_run(
                session=session,
                run_record=audit_run,
                records_extracted=total_extracted,
                records_loaded=total_clean_loaded,
                records_quarantined=len(quarantine_records),
                error_summary=None,
            )

            pass_rate = (
                round((total_clean_loaded / total_extracted) * 100, 2)
                if total_extracted > 0
                else 100.0
            )

            summary = {
                "run_id": run_id,
                "status": audit_run.status,
                "duration_seconds": audit_run.execution_time_seconds,
                "records_extracted": total_extracted,
                "records_loaded": total_clean_loaded,
                "records_quarantined": len(quarantine_records),
                "data_quality_pass_rate_pct": pass_rate,
                "by_entity": val_metrics["entities"],
                "quarantine_summary": quarantine_summary,
            }

            logger.info("=" * 80)
            logger.info(
                f"PIPELINE COMPLETED: Status={audit_run.status} | "
                f"Loaded={total_clean_loaded} | Quarantined={len(quarantine_records)} | "
                f"Pass Rate={pass_rate}% | Duration={audit_run.execution_time_seconds}s"
            )
            logger.info("=" * 80)
            return summary

        except Exception as e:
            logger.exception(f"Fatal error during pipeline run {run_id}: {e}")
            if run_id:
                # Attempt to update run record to FAILED
                try:
                    fail_run = session.get(EtlPipelineRun, run_id)
                    if fail_run:
                        finish_pipeline_run(
                            session=session,
                            run_record=fail_run,
                            records_extracted=0,
                            records_loaded=0,
                            records_quarantined=0,
                            error_summary=str(e),
                        )
                except Exception as audit_err:
                    logger.error(f"Failed to record audit failure: {audit_err}")
            raise
