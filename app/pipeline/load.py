"""Database Loading Layer: Idempotent upsert logic and transaction management."""

import logging
from typing import Any, Dict, List, Type
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.database.models import (
    Base,
    DimSite,
    DimSubject,
    FactLabResult,
    FactVisit,
    QuarantineRecord,
)

logger = logging.getLogger(__name__)


def upsert_records(
    session: Session,
    model_class: Type[Base],
    records: List[Dict[str, Any]],
    pk_column: str,
) -> int:
    """Execute idempotent upsert across PostgreSQL or SQLite.

    If a record with pk_column already exists, all non-PK columns are updated.
    If it does not exist, it is inserted.
    """
    if not records:
        return 0

    dialect_name = session.bind.dialect.name

    if dialect_name == "postgresql":
        # Native PostgreSQL ON CONFLICT DO UPDATE
        for record in records:
            stmt = pg_insert(model_class).values(record)
            update_cols = {col: stmt.excluded[col] for col in record if col != pk_column}
            if update_cols:
                stmt = stmt.on_conflict_do_update(
                    index_elements=[pk_column],
                    set_=update_cols,
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=[pk_column])
            session.execute(stmt)

    elif dialect_name == "sqlite":
        # Native SQLite ON CONFLICT DO UPDATE (supported in SQLite 3.24+)
        for record in records:
            stmt = sqlite_insert(model_class).values(record)
            update_cols = {col: stmt.excluded[col] for col in record if col != pk_column}
            if update_cols:
                stmt = stmt.on_conflict_do_update(
                    index_elements=[pk_column],
                    set_=update_cols,
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=[pk_column])
            session.execute(stmt)

    else:
        # Fallback ORM merge
        for record in records:
            existing = session.execute(
                select(model_class).filter_by(**{pk_column: record[pk_column]})
            ).scalar_one_or_none()
            if existing:
                for k, v in record.items():
                    if k != pk_column:
                        setattr(existing, k, v)
            else:
                session.add(model_class(**record))

    return len(records)


def df_to_clean_dicts(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert pandas DataFrame rows to clean Python dicts with None instead of NaN."""
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col, val in row.items():
            if pd.isna(val):
                rec[col] = None
            else:
                rec[col] = val
        records.append(rec)
    return records


def load_clean_data(
    session: Session,
    clean_datasets: Dict[str, pd.DataFrame],
    quarantine_records: List[QuarantineRecord],
) -> Dict[str, int]:
    """Load all validated clean records and quarantine records in dependency order.

    Order of execution to preserve foreign key constraints:
    1. DimSite
    2. DimSubject
    3. FactVisit
    4. FactLabResult
    5. QuarantineRecord

    Returns:
        Dict mapping table names to number of records loaded.
    """
    loaded_counts: Dict[str, int] = {}

    # 1. Sites
    sites_data = df_to_clean_dicts(clean_datasets["sites"])
    count_sites = upsert_records(session, DimSite, sites_data, pk_column="site_id")
    loaded_counts["dim_sites"] = count_sites
    session.flush()

    # 2. Subjects
    subj_data = df_to_clean_dicts(clean_datasets["subjects"])
    count_subj = upsert_records(session, DimSubject, subj_data, pk_column="subject_id")
    loaded_counts["dim_subjects"] = count_subj
    session.flush()

    # 3. Visits
    visits_data = df_to_clean_dicts(clean_datasets["visits"])
    count_visits = upsert_records(session, FactVisit, visits_data, pk_column="visit_id")
    loaded_counts["fact_visits"] = count_visits
    session.flush()

    # 4. Lab Results
    labs_data = df_to_clean_dicts(clean_datasets["lab_results"])
    count_labs = upsert_records(session, FactLabResult, labs_data, pk_column="result_id")
    loaded_counts["fact_lab_results"] = count_labs
    session.flush()

    # 5. Quarantine Records
    if quarantine_records:
        session.add_all(quarantine_records)
        session.flush()
    loaded_counts["quarantine_records"] = len(quarantine_records)

    logger.info(f"Loaded records to database: {loaded_counts}")
    return loaded_counts
