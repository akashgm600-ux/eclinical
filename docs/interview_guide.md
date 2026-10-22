# Technical Interview Guide: Clinical Trial Data Quality & ETL Pipeline

This guide provides targeted talking points, architectural rationale, and structured interview answers to showcase this project during technical screens and hiring manager discussions for **Data Engineer II** and **Senior Data Engineer** roles.

---

## 1. The 60-Second "Elevator Pitch" (STAR Method)

> **Situation:** 
> "In clinical trials, data integrity is strictly regulated under FDA 21 CFR Part 11 and CDISC standards. Dropping invalid rows silently or corrupting temporal sequences can invalidate an entire drug submission or mask patient safety signals."
>
> **Task:** 
> "I built an end-to-end, production-grade Clinical Trial Data Quality & ETL Pipeline that ingests multi-entity clinical data (Sites, Subjects, Visits, Lab Results), enforces multi-tiered data quality gates, guarantees zero silent data loss via an automated quarantine store, loads valid records idempotently into PostgreSQL, and surfaces real-time quality observability via Streamlit and FastAPI."
>
> **Action:** 
> "I designed the system using Python 3.12, Pandas, and SQLAlchemy 2.0. I implemented hierarchical rule validation that protects referential integrity prior to database ingestion, structured cryptographic SHA-256 file hashing for auditability, native `ON CONFLICT DO UPDATE` upserts for re-run idempotency, and a complete Pytest suite with 100% deterministic test fixtures and sub-second execution."
>
> **Result:** 
> "The pipeline achieved sub-second execution speeds, automated quarantine routing with full raw JSON preservation, 0% duplicate accumulation across redundant executions, and comprehensive operational dashboards delivering real-time pass-rate metrics."

---

## 2. Core Architectural Decisions & Trade-Offs

### Q1: Why use Pandas instead of PySpark or Apache Beam?
- **Trade-off:**
  - *PySpark:* Distributed computing is optimal for terabyte-scale log streams or genomics, but introduces cluster management complexity, JVM overhead, network serialization bottlenecks, and higher cloud compute costs for clinical study batches.
  - *Pandas:* Clinical trial batches for Phase I–III trials typically range from tens of thousands to a few million rows per transfer batch. Pandas executes entirely in-memory with vectorized C/Cython operations, offering microsecond latency, zero cluster overhead, and simple deployment inside lightweight Docker containers.
- **Scale-Up Strategy:**
  - "If data volumes exceed single-node memory (e.g. continuous wearable sensor data), the modular architecture allows swapping the transform and validation engine to Polars (for multi-threaded memory efficiency) or PySpark with minimal changes to the database and API layers."

### Q2: Why implement a Quarantine Table instead of just rejecting batches or using `.dropna()`?
- **Trade-off:**
  - *Dropping bad rows (`.dropna()`):* Unacceptable in clinical trials. Dropping a row with `ALT = 9999` or an impossible negative lab value masks acute adverse events and violates ALCOA+ completeness.
  - *Failing the whole batch:* Halts the entire clinical data pipeline for days while awaiting query resolution from a single investigational site.
  - *Quarantine Architecture:* Valid data flows freely into analytics and biostatistics views, while invalid rows are captured in `quarantine_records` alongside their raw JSON payload, exact error code, and run metadata. Site monitors can triage discrepancies asynchronously without stalling study operations.

### Q3: How do you guarantee Idempotency across pipeline reruns?
- **Trade-off:**
  - *Truncate and Reload:* Simple, but destroys historical data, wipes out existing foreign key relationships, locks database tables, and breaks audit trails.
  - *Native UPSERT (`ON CONFLICT DO UPDATE`):* We use SQLAlchemy dialect-specific upserts. On PostgreSQL, `ON CONFLICT (site_id) DO UPDATE` refreshes modified fields in-place; on duplicate records with no changes, it performs a no-op. Rerunning the pipeline on the same file 10 times yields the exact same clean database state without primary key collisions or duplicate row inflation.

### Q4: How do you handle Referential Integrity in Python before loading into the Database?
- **Trade-off:**
  - If we rely solely on PostgreSQL foreign key constraints to catch orphan records, a single bad subject row referencing a missing site causes the entire database transaction to crash with a `ForeignKeyViolation` error.
  - *Our Solution:* We validate in relational order:
    1. Validate `Sites` ➔ Establish set of verified `valid_site_ids`.
    2. Validate `Subjects` ➔ Check foreign keys against `valid_site_ids`. If a site failed, quarantine its subjects in Python.
    3. Validate `Visits` ➔ Check foreign keys against clean subjects.
    4. Validate `Lab Results` ➔ Check against clean visits and clean subjects.
  - *Outcome:* The database transaction succeeds with 100% clean, non-conflicting relational records, while orphan records are cleanly routed to quarantine with informative diagnostics.

---

## 3. High-Frequency Technical Interview Questions & Answers

### Question: "How would you monitor this pipeline in a production cloud environment?"
**Talking Points:**
1. **Orchestration:** Deploy DAGs in Apache Airflow or Prefect to schedule batches and handle retries with exponential backoff.
2. **Metrics & Alerting:** Export Prometheus metrics from the FastAPI service; configure alerts on Slack/PagerDuty if `data_quality_pass_rate_pct < 85%` or if pipeline status equals `FAILED`.
3. **Log Aggregation:** Ship rotating logs to AWS CloudWatch, Datadog, or Grafana Loki with structured JSON fields (`run_id`, `rule_code`, `records_extracted`).

### Question: "How would you handle schema drift (e.g. upstream site adds a new unexpected column)?"
**Talking Points:**
1. Our `extract.py` checks for the presence of *required* columns rather than failing on extra unexpected columns.
2. If unexpected columns are detected, we log a `WARNING` and store the full unedited row in `quarantine_records` or pass them through a semi-structured JSONB metadata column.
3. If a mandatory column is deleted or renamed, `extract.py` immediately halts with a clean `ExtractionError` before transforming bad data.

### Question: "Why did you write 27 automated unit tests instead of just manually clicking through the Streamlit dashboard?"
**Talking Points:**
- "In regulated clinical software (GxP), software validation requires deterministic, repeatable, and automated testing to ensure regression safety. My test suite covers schema validation, string cleansing, categorical rules, date parsing, referential integrity cascades, database rollbacks on simulated mid-flight errors, and API integration. All tests run in ~1.5 seconds using an in-memory SQLite database, enabling frictionless CI/CD verification."
