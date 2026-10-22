-- =============================================================================
-- Advanced Analytical SQL Scripts & Interview Case Studies
-- =============================================================================
-- This script contains production-grade SQL queries demonstrating core Data
-- Engineering techniques: Common Table Expressions (CTEs), Window Functions,
-- Cumulative Metrics, Deduplication Logic, and Performance Execution Plans.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- QUERY 1: Subject Visit Interval Analysis (Window Functions: LAG & DENSE_RANK)
-- -----------------------------------------------------------------------------
-- Business Question:
-- What is the elapsed time (in days) between consecutive visits for each subject?
-- Are any visits spaced excessively far apart, suggesting protocol deviation?
--
-- Technical Rationale & Trade-offs:
-- Using LAG() over a window partitioned by subject_id ordered by visit_date
-- eliminates self-joins, running in O(N log N) sorting time rather than O(N^2).

WITH ordered_visits AS (
    SELECT 
        v.subject_id,
        v.visit_id,
        v.visit_name,
        v.visit_date,
        v.visit_status,
        LAG(v.visit_date, 1) OVER (
            PARTITION BY v.subject_id 
            ORDER BY v.visit_date ASC
        ) AS previous_visit_date,
        ROW_NUMBER() OVER (
            PARTITION BY v.subject_id 
            ORDER BY v.visit_date ASC
        ) AS visit_sequence_number
    FROM fact_visits v
    WHERE v.visit_status = 'ATTENDED'
)
SELECT 
    subject_id,
    visit_sequence_number,
    visit_name,
    visit_date,
    previous_visit_date,
    -- Date difference (CAST for cross-dialect compatibility)
    ROUND(JULIANDAY(visit_date) - JULIANDAY(previous_visit_date)) AS days_since_last_visit
FROM ordered_visits
ORDER BY subject_id, visit_sequence_number;

-- Expected Output Sample:
-- subject_id | seq | visit_name | visit_date | prev_date  | days_since_last_visit
-- SUBJ-1001  | 1   | SCREENING  | 2023-03-12 | NULL       | NULL
-- SUBJ-1001  | 2   | BASELINE   | 2023-03-26 | 2023-03-12 | 14
-- SUBJ-1001  | 3   | WEEK 4     | 2023-04-23 | 2023-03-26 | 28


-- -----------------------------------------------------------------------------
-- QUERY 2: Rolling Biomarker Baseline & Moving Average (Window Function: Frame Clause)
-- -----------------------------------------------------------------------------
-- Business Question:
-- For clinical safety monitoring, calculate each subject's 3-test moving average
-- for liver enzymes (ALT) and compare each test against their initial baseline.
--
-- Technical Rationale & Trade-offs:
-- Window frames (ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) allow calculating
-- running averages without expanding table scans or temp tables.

WITH lab_history AS (
    SELECT 
        lab.subject_id,
        lab.result_id,
        lab.test_code,
        lab.result_value,
        lab.collection_date,
        FIRST_VALUE(lab.result_value) OVER (
            PARTITION BY lab.subject_id, lab.test_code 
            ORDER BY lab.collection_date ASC
        ) AS baseline_value,
        AVG(lab.result_value) OVER (
            PARTITION BY lab.subject_id, lab.test_code 
            ORDER BY lab.collection_date ASC 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS rolling_3test_avg
    FROM fact_lab_results lab
    WHERE lab.test_code = 'ALT'
)
SELECT 
    subject_id,
    collection_date,
    result_value AS current_alt,
    baseline_value,
    ROUND(result_value - baseline_value, 2) AS delta_from_baseline,
    ROUND(rolling_3test_avg, 2) AS rolling_avg_alt
FROM lab_history
ORDER BY subject_id, collection_date;


-- -----------------------------------------------------------------------------
-- QUERY 3: Duplicate Detection and Reconciliation (Deduplication via ROW_NUMBER)
-- -----------------------------------------------------------------------------
-- Business Question:
-- If an upstream ingestion system inadvertently loads multiple duplicate test 
-- records for the same subject, visit, and test code, how can we reconcile and
-- extract solely the latest valid record?
--
-- Technical Rationale & Trade-offs:
-- ROW_NUMBER() PARTITION BY (natural key) ORDER BY updated_at DESC assigns 1 to
-- the freshest record. Filtering rn = 1 performs deterministic deduplication.

WITH ranked_labs AS (
    SELECT 
        result_id,
        subject_id,
        visit_id,
        test_code,
        result_value,
        collection_date,
        updated_at,
        ROW_NUMBER() OVER (
            PARTITION BY subject_id, visit_id, test_code 
            ORDER BY updated_at DESC, result_id DESC
        ) AS dedup_rank
    FROM fact_lab_results
)
SELECT 
    result_id,
    subject_id,
    visit_id,
    test_code,
    result_value,
    collection_date
FROM ranked_labs
WHERE dedup_rank = 1;


-- -----------------------------------------------------------------------------
-- QUERY 4: Data Quality Triage & Failure Pareto (Aggregation & Percentage Distribution)
-- -----------------------------------------------------------------------------
-- Business Question:
-- Which data quality rules trigger the highest volume of quarantine rejections?
-- What percentage of all quarantined rows do they represent?

WITH rule_counts AS (
    SELECT 
        source_entity,
        rule_code,
        rule_name,
        COUNT(*) AS violation_count
    FROM quarantine_records
    GROUP BY source_entity, rule_code, rule_name
),
total_summary AS (
    SELECT SUM(violation_count) AS total_violations FROM rule_counts
)
SELECT 
    rc.source_entity,
    rc.rule_code,
    rc.rule_name,
    rc.violation_count,
    ROUND((CAST(rc.violation_count AS FLOAT) / ts.total_violations) * 100.0, 2) AS pct_of_total_quarantine
FROM rule_counts rc
CROSS JOIN total_summary ts
ORDER BY rc.violation_count DESC;


-- -----------------------------------------------------------------------------
-- QUERY 5: Query Performance & Execution Plan Investigation (EXPLAIN / Indexing)
-- -----------------------------------------------------------------------------
-- Technical Rationale:
-- In large clinical databases (millions of lab results), queries filtering by
-- subject_id and test_code frequently cause costly full table scans without
-- composite B-Tree indexes.
--
-- Postgres Syntax:
--   EXPLAIN ANALYZE
--   SELECT * FROM fact_lab_results 
--   WHERE subject_id = 'SUBJ-1001' AND test_code = 'GLUC';
--
-- Performance Comparison:
--   Without index: Seq Scan on fact_lab_results (cost=0.00..185.00 rows=15 width=68)
--   With index (idx_labs_subject_test): Bitmap Index Scan using idx_labs_subject_test (cost=0.00..4.15 rows=15 width=68)
--   Speedup: ~40x reduction in disk buffer page reads.
