-- =============================================================================
-- Clinical Trial Reporting and Operational Database Views
-- Compatible with PostgreSQL and SQLite
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. View: Study Site Performance and Compliance Summary
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_site_metrics;
CREATE VIEW vw_site_metrics AS
SELECT 
    s.site_id,
    s.site_name,
    s.country,
    s.status AS site_status,
    COUNT(DISTINCT subj.subject_id) AS total_subjects_enrolled,
    COUNT(DISTINCT v.visit_id) AS total_visits_scheduled,
    COUNT(DISTINCT CASE WHEN v.visit_status = 'ATTENDED' THEN v.visit_id END) AS visits_attended,
    COUNT(DISTINCT CASE WHEN v.visit_status = 'MISSED' THEN v.visit_id END) AS visits_missed,
    ROUND(
        CASE 
            WHEN COUNT(DISTINCT v.visit_id) > 0 
            THEN (CAST(COUNT(DISTINCT CASE WHEN v.visit_status = 'ATTENDED' THEN v.visit_id END) AS FLOAT) / COUNT(DISTINCT v.visit_id)) * 100.0
            ELSE 0.0 
        END, 2
    ) AS visit_attendance_rate_pct,
    COUNT(DISTINCT lab.result_id) AS total_lab_tests_performed
FROM dim_sites s
LEFT JOIN dim_subjects subj ON s.site_id = subj.site_id
LEFT JOIN fact_visits v ON subj.subject_id = v.subject_id
LEFT JOIN fact_lab_results lab ON v.visit_id = lab.visit_id
GROUP BY s.site_id, s.site_name, s.country, s.status;

-- -----------------------------------------------------------------------------
-- 2. View: Data Quality and Pipeline Run Audit Summary
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_data_quality_summary;
CREATE VIEW vw_data_quality_summary AS
SELECT 
    r.run_id,
    r.start_time,
    r.status AS run_status,
    r.execution_time_seconds,
    r.records_extracted,
    r.records_loaded,
    r.records_quarantined,
    ROUND(
        CASE 
            WHEN r.records_extracted > 0 
            THEN (CAST(r.records_loaded AS FLOAT) / r.records_extracted) * 100.0
            ELSE 100.0 
        END, 2
    ) AS data_quality_pass_rate_pct,
    COUNT(DISTINCT q.id) AS total_quarantine_violations_recorded,
    COUNT(DISTINCT q.rule_code) AS unique_rules_violated
FROM etl_pipeline_runs r
LEFT JOIN quarantine_records q ON r.run_id = q.run_id
GROUP BY 
    r.run_id, r.start_time, r.status, r.execution_time_seconds, 
    r.records_extracted, r.records_loaded, r.records_quarantined;

-- -----------------------------------------------------------------------------
-- 3. View: Subject Adherence and Lab Abnormality Profile
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_subject_compliance;
CREATE VIEW vw_subject_compliance AS
SELECT 
    subj.subject_id,
    subj.site_id,
    subj.status AS subject_status,
    subj.enrollment_date,
    COUNT(DISTINCT v.visit_id) AS total_visits,
    COUNT(DISTINCT CASE WHEN v.visit_status = 'ATTENDED' THEN v.visit_id END) AS attended_visits,
    COUNT(DISTINCT lab.result_id) AS total_lab_assessments,
    COUNT(DISTINCT CASE WHEN lab.abnormal_flag IN ('HIGH', 'LOW', 'CRITICAL') THEN lab.result_id END) AS abnormal_lab_count,
    ROUND(
        CASE 
            WHEN COUNT(DISTINCT lab.result_id) > 0 
            THEN (CAST(COUNT(DISTINCT CASE WHEN lab.abnormal_flag IN ('HIGH', 'LOW', 'CRITICAL') THEN lab.result_id END) AS FLOAT) / COUNT(DISTINCT lab.result_id)) * 100.0
            ELSE 0.0 
        END, 2
    ) AS lab_abnormality_rate_pct
FROM dim_subjects subj
LEFT JOIN fact_visits v ON subj.subject_id = v.subject_id
LEFT JOIN fact_lab_results lab ON subj.subject_id = lab.subject_id
GROUP BY subj.subject_id, subj.site_id, subj.status, subj.enrollment_date;
