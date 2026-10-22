"""FastAPI route handlers for pipeline management, data quality, and quarantine inspection."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db_session
from app.database.models import EtlPipelineRun, QuarantineRecord
from app.pipeline.runner import run_pipeline

router = APIRouter()


# -----------------------------------------------------------------------------
# Pydantic Response Models
# -----------------------------------------------------------------------------
class HealthCheckResponse(BaseModel):
    status: str
    database: str
    pipeline_version: str


class PipelineRunResponse(BaseModel):
    run_id: str
    pipeline_name: str
    pipeline_version: str
    start_time: str
    end_time: Optional[str] = None
    status: str
    records_extracted: int
    records_loaded: int
    records_quarantined: int
    execution_time_seconds: float
    error_summary: Optional[str] = None

    class Config:
        from_attributes = True


class QuarantineRecordResponse(BaseModel):
    id: int
    run_id: str
    source_entity: str
    record_identifier: Optional[str] = None
    raw_record: str
    rule_code: str
    rule_name: str
    error_message: str
    severity: str
    quarantined_at: str

    class Config:
        from_attributes = True


class QualitySummaryMetrics(BaseModel):
    total_runs: int
    successful_runs: int
    partial_success_runs: int
    failed_runs: int
    total_records_extracted: int
    total_records_loaded: int
    total_records_quarantined: int
    overall_pass_rate_pct: float
    most_frequent_quarantine_rules: List[Dict[str, Any]]


class TriggerRunRequest(BaseModel):
    input_dir: Optional[str] = None


# -----------------------------------------------------------------------------
# Route Endpoints
# -----------------------------------------------------------------------------
@router.get("/health", response_model=HealthCheckResponse, tags=["System"])
def get_health():
    """Verify application operational health and database connectivity."""
    db_status = "healthy"
    try:
        with get_db_session() as session:
            session.execute(select(1)).scalar()
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return HealthCheckResponse(
        status="healthy" if "unhealthy" not in db_status else "degraded",
        database=db_status,
        pipeline_version=settings.PIPELINE_VERSION,
    )


@router.get("/runs", response_model=List[PipelineRunResponse], tags=["Pipeline Runs"])
def list_pipeline_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Retrieve history of pipeline executions ordered by start time descending."""
    with get_db_session() as session:
        query = (
            select(EtlPipelineRun)
            .order_by(desc(EtlPipelineRun.start_time))
            .offset(offset)
            .limit(limit)
        )
        runs = session.execute(query).scalars().all()
        return [
            PipelineRunResponse(
                run_id=r.run_id,
                pipeline_name=r.pipeline_name,
                pipeline_version=r.pipeline_version,
                start_time=r.start_time.isoformat(),
                end_time=r.end_time.isoformat() if r.end_time else None,
                status=r.status,
                records_extracted=r.records_extracted,
                records_loaded=r.records_loaded,
                records_quarantined=r.records_quarantined,
                execution_time_seconds=r.execution_time_seconds,
                error_summary=r.error_summary,
            )
            for r in runs
        ]


@router.get("/runs/{run_id}", response_model=PipelineRunResponse, tags=["Pipeline Runs"])
def get_pipeline_run(run_id: str):
    """Retrieve execution metrics for a specific pipeline run ID."""
    with get_db_session() as session:
        run = session.get(EtlPipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found.")
        return PipelineRunResponse(
            run_id=run.run_id,
            pipeline_name=run.pipeline_name,
            pipeline_version=run.pipeline_version,
            start_time=run.start_time.isoformat(),
            end_time=run.end_time.isoformat() if run.end_time else None,
            status=run.status,
            records_extracted=run.records_extracted,
            records_loaded=run.records_loaded,
            records_quarantined=run.records_quarantined,
            execution_time_seconds=run.execution_time_seconds,
            error_summary=run.error_summary,
        )


@router.get("/quarantine", response_model=List[QuarantineRecordResponse], tags=["Data Quality"])
def get_quarantine_records(
    run_id: Optional[str] = Query(None, description="Filter by pipeline run ID"),
    entity: Optional[str] = Query(None, description="Filter by entity name (sites, subjects, visits, lab_results)"),
    rule_code: Optional[str] = Query(None, description="Filter by rule code"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Inspect rejected records in quarantine with optional filtering."""
    with get_db_session() as session:
        query = select(QuarantineRecord).order_by(desc(QuarantineRecord.quarantined_at))
        if run_id:
            query = query.filter(QuarantineRecord.run_id == run_id)
        if entity:
            query = query.filter(QuarantineRecord.source_entity == entity)
        if rule_code:
            query = query.filter(QuarantineRecord.rule_code == rule_code)

        records = session.execute(query.offset(offset).limit(limit)).scalars().all()
        return [
            QuarantineRecordResponse(
                id=q.id,
                run_id=q.run_id,
                source_entity=q.source_entity,
                record_identifier=q.record_identifier,
                raw_record=q.raw_record,
                rule_code=q.rule_code,
                rule_name=q.rule_name,
                error_message=q.error_message,
                severity=q.severity,
                quarantined_at=q.quarantined_at.isoformat(),
            )
            for q in records
        ]


@router.get("/metrics/summary", response_model=QualitySummaryMetrics, tags=["Data Quality"])
def get_quality_summary_metrics():
    """Aggregate high-level platform quality metrics across all runs."""
    with get_db_session() as session:
        runs = session.execute(select(EtlPipelineRun)).scalars().all()
        total_runs = len(runs)
        if total_runs == 0:
            return QualitySummaryMetrics(
                total_runs=0,
                successful_runs=0,
                partial_success_runs=0,
                failed_runs=0,
                total_records_extracted=0,
                total_records_loaded=0,
                total_records_quarantined=0,
                overall_pass_rate_pct=100.0,
                most_frequent_quarantine_rules=[],
            )

        success = sum(1 for r in runs if r.status == "SUCCESS")
        partial = sum(1 for r in runs if r.status == "PARTIAL_SUCCESS")
        failed = sum(1 for r in runs if r.status == "FAILED")
        extracted = sum(r.records_extracted for r in runs)
        loaded = sum(r.records_loaded for r in runs)
        quarantined = sum(r.records_quarantined for r in runs)

        pass_rate = round((loaded / extracted) * 100.0, 2) if extracted > 0 else 100.0

        # Top violated rules query
        rule_counts = (
            session.execute(
                select(
                    QuarantineRecord.rule_code,
                    QuarantineRecord.rule_name,
                    func.count(QuarantineRecord.id).label("count"),
                )
                .group_by(QuarantineRecord.rule_code, QuarantineRecord.rule_name)
                .order_by(desc("count"))
                .limit(5)
            )
            .all()
        )

        top_rules = [
            {"rule_code": r[0], "rule_name": r[1], "violations": r[2]}
            for r in rule_counts
        ]

        return QualitySummaryMetrics(
            total_runs=total_runs,
            successful_runs=success,
            partial_success_runs=partial,
            failed_runs=failed,
            total_records_extracted=extracted,
            total_records_loaded=loaded,
            total_records_quarantined=quarantined,
            overall_pass_rate_pct=pass_rate,
            most_frequent_quarantine_rules=top_rules,
        )


@router.post("/pipeline/trigger", tags=["Pipeline Execution"])
def trigger_pipeline(request: TriggerRunRequest = TriggerRunRequest()):
    """Manually initiate a pipeline execution run."""
    try:
        summary = run_pipeline(input_dir=request.input_dir)
        return {"message": "Pipeline run completed successfully.", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {str(e)}")
