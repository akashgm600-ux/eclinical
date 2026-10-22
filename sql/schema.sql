-- =============================================================================
-- Clinical Trial Data Platform: Database Schema Definition (PostgreSQL 16+)
-- =============================================================================

-- Enable UUID extension if needed in PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 1. Dimension: Study Sites (dim_sites)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_sites (
    site_id VARCHAR(50) PRIMARY KEY,
    site_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    investigator_name VARCHAR(255),
    activation_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_site_status CHECK (status IN ('ACTIVE', 'CLOSED', 'SUSPENDED'))
);

COMMENT ON TABLE dim_sites IS 'Dimension table storing clinical trial investigative sites.';
COMMENT ON COLUMN dim_sites.site_id IS 'Unique identifier for clinical research site (e.g., SITE-101).';
COMMENT ON COLUMN dim_sites.status IS 'Operational status of the site: ACTIVE, CLOSED, or SUSPENDED.';

-- -----------------------------------------------------------------------------
-- 2. Dimension: Subjects / Patients (dim_subjects)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_subjects (
    subject_id VARCHAR(50) PRIMARY KEY,
    site_id VARCHAR(50) NOT NULL,
    enrollment_date DATE NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(20),
    status VARCHAR(50) NOT NULL DEFAULT 'ENROLLED',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_subjects_site FOREIGN KEY (site_id) 
        REFERENCES dim_sites(site_id) ON DELETE RESTRICT,
    CONSTRAINT chk_subject_status CHECK (status IN ('ENROLLED', 'ACTIVE', 'COMPLETED', 'WITHDRAWN', 'SCREEN_FAIL')),
    CONSTRAINT chk_subject_gender CHECK (gender IN ('M', 'F', 'OTHER', NULL))
);

CREATE INDEX IF NOT EXISTS idx_subjects_site_id ON dim_subjects(site_id);
CREATE INDEX IF NOT EXISTS idx_subjects_status ON dim_subjects(status);

COMMENT ON TABLE dim_subjects IS 'Dimension table storing enrolled clinical trial participants.';
COMMENT ON COLUMN dim_subjects.subject_id IS 'Unique participant identifier across study (e.g., SUBJ-1001).';
COMMENT ON COLUMN dim_subjects.site_id IS 'Investigative site where subject is registered.';

-- -----------------------------------------------------------------------------
-- 3. Fact: Protocol Visits (fact_visits)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_visits (
    visit_id VARCHAR(50) PRIMARY KEY,
    subject_id VARCHAR(50) NOT NULL,
    visit_name VARCHAR(100) NOT NULL,
    visit_date DATE NOT NULL,
    visit_status VARCHAR(50) NOT NULL DEFAULT 'ATTENDED',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_visits_subject FOREIGN KEY (subject_id) 
        REFERENCES dim_subjects(subject_id) ON DELETE CASCADE,
    CONSTRAINT chk_visit_status CHECK (visit_status IN ('ATTENDED', 'MISSED', 'CANCELLED', 'SCHEDULED'))
);

CREATE INDEX IF NOT EXISTS idx_visits_subject_id ON fact_visits(subject_id);
CREATE INDEX IF NOT EXISTS idx_visits_date ON fact_visits(visit_date);

COMMENT ON TABLE fact_visits IS 'Fact table capturing scheduled and unscheduled study visits.';
COMMENT ON COLUMN fact_visits.visit_id IS 'Unique visit identifier (e.g., VIS-5001).';

-- -----------------------------------------------------------------------------
-- 4. Fact: Laboratory Results (fact_lab_results)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_lab_results (
    result_id VARCHAR(50) PRIMARY KEY,
    visit_id VARCHAR(50) NOT NULL,
    subject_id VARCHAR(50) NOT NULL,
    test_code VARCHAR(50) NOT NULL,
    test_name VARCHAR(150) NOT NULL,
    result_value NUMERIC(12, 4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    reference_low NUMERIC(12, 4),
    reference_high NUMERIC(12, 4),
    collection_date DATE NOT NULL,
    abnormal_flag VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_labs_visit FOREIGN KEY (visit_id) 
        REFERENCES fact_visits(visit_id) ON DELETE CASCADE,
    CONSTRAINT fk_labs_subject FOREIGN KEY (subject_id) 
        REFERENCES dim_subjects(subject_id) ON DELETE CASCADE,
    CONSTRAINT chk_abnormal_flag CHECK (abnormal_flag IN ('NORMAL', 'HIGH', 'LOW', 'CRITICAL'))
);

CREATE INDEX IF NOT EXISTS idx_labs_subject_id ON fact_lab_results(subject_id);
CREATE INDEX IF NOT EXISTS idx_labs_visit_id ON fact_lab_results(visit_id);
CREATE INDEX IF NOT EXISTS idx_labs_test_code ON fact_lab_results(test_code);
CREATE INDEX IF NOT EXISTS idx_labs_collection_date ON fact_lab_results(collection_date);

COMMENT ON TABLE fact_lab_results IS 'Fact table recording quantitative laboratory assessments.';

-- -----------------------------------------------------------------------------
-- 5. Audit: Pipeline Execution Tracking (etl_pipeline_runs)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_pipeline_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    pipeline_version VARCHAR(50) NOT NULL,
    start_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_time TIMESTAMP WITHOUT TIME ZONE,
    status VARCHAR(50) NOT NULL DEFAULT 'STARTED',
    records_extracted INTEGER NOT NULL DEFAULT 0,
    records_loaded INTEGER NOT NULL DEFAULT 0,
    records_quarantined INTEGER NOT NULL DEFAULT 0,
    execution_time_seconds NUMERIC(10, 3) NOT NULL DEFAULT 0.0,
    error_summary TEXT,
    CONSTRAINT chk_run_status CHECK (status IN ('STARTED', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_runs_start_time ON etl_pipeline_runs(start_time DESC);

COMMENT ON TABLE etl_pipeline_runs IS 'Tracks metadata and health metrics for each pipeline execution.';

-- -----------------------------------------------------------------------------
-- 6. Audit & Recovery: Data Quality Quarantine (quarantine_records)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quarantine_records (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    source_entity VARCHAR(50) NOT NULL,
    record_identifier VARCHAR(100),
    raw_record TEXT NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    error_message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'ERROR',
    quarantined_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_quarantine_run FOREIGN KEY (run_id) 
        REFERENCES etl_pipeline_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT chk_quarantine_severity CHECK (severity IN ('ERROR', 'WARNING'))
);

CREATE INDEX IF NOT EXISTS idx_quarantine_run_id ON quarantine_records(run_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_entity ON quarantine_records(source_entity);
CREATE INDEX IF NOT EXISTS idx_quarantine_rule ON quarantine_records(rule_code);
CREATE INDEX IF NOT EXISTS idx_quarantine_date ON quarantine_records(quarantined_at DESC);

COMMENT ON TABLE quarantine_records IS 'Holds rejected records that violated data quality rules.';
