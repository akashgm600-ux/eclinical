"""Streamlit Interactive Data Quality & Clinical Trial Observability Dashboard."""

from datetime import datetime
import json
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import desc, select

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.database.connection import get_db_session, get_engine
from app.database.models import (
    DimSite,
    DimSubject,
    EtlPipelineRun,
    FactLabResult,
    FactVisit,
    QuarantineRecord,
)
from app.pipeline.runner import run_pipeline

st.set_page_config(
    page_title="Clinical Trial ETL & Data Quality Observability",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .status-badge-success { color: #2e7d32; font-weight: bold; }
    .status-badge-partial { color: #f57f17; font-weight: bold; }
    .status-badge-failed { color: #c62828; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_runs_data() -> pd.DataFrame:
    """Fetch pipeline runs from database."""
    engine = get_engine()
    query = """
        SELECT 
            run_id, pipeline_name, start_time, end_time, status,
            records_extracted, records_loaded, records_quarantined,
            execution_time_seconds, error_summary,
            ROUND(
                CASE WHEN records_extracted > 0 
                THEN (CAST(records_loaded AS FLOAT) / records_extracted) * 100.0 
                ELSE 100.0 END, 2
            ) AS pass_rate_pct
        FROM etl_pipeline_runs 
        ORDER BY start_time DESC
    """
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return pd.DataFrame()


def load_quarantine_data(run_id: str = None) -> pd.DataFrame:
    """Fetch quarantine records from database."""
    engine = get_engine()
    query = "SELECT * FROM quarantine_records"
    if run_id and run_id != "All Runs":
        query += f" WHERE run_id = '{run_id}'"
    query += " ORDER BY quarantined_at DESC LIMIT 1000"
    try:
        return pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame()


def load_site_metrics() -> pd.DataFrame:
    """Fetch site metrics from view."""
    engine = get_engine()
    try:
        return pd.read_sql("SELECT * FROM vw_site_metrics", engine)
    except Exception:
        return pd.DataFrame()


def load_subject_metrics() -> pd.DataFrame:
    """Fetch subject compliance metrics from view."""
    engine = get_engine()
    try:
        return pd.read_sql("SELECT * FROM vw_subject_compliance", engine)
    except Exception:
        return pd.DataFrame()


def load_lab_data() -> pd.DataFrame:
    """Fetch lab distribution metrics."""
    engine = get_engine()
    try:
        return pd.read_sql("SELECT * FROM fact_lab_results LIMIT 1000", engine)
    except Exception:
        return pd.DataFrame()


# -----------------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🧬 Clinical Trial ETL")
    st.markdown("**Data Quality & Ingestion Engine**")
    st.caption("Demonstrating Zero-Silent-Loss ETL with PostgreSQL & Streamlit")
    st.divider()

    st.subheader("Pipeline Trigger")
    if st.button("🚀 Trigger Ingestion Run", use_container_width=True, type="primary"):
        with st.spinner("Executing pipeline (Extract ➔ Transform ➔ Validate ➔ Load)..."):
            try:
                res = run_pipeline()
                st.success(f"Run Completed! Status: {res['status']}")
                st.rerun()
            except Exception as ex:
                st.error(f"Pipeline Failed: {ex}")

    st.divider()
    st.caption("Database Target:")
    st.code(settings.DATABASE_URL.split("@")[-1], language="text")
    st.caption(f"Pipeline Version: {settings.PIPELINE_VERSION}")


# -----------------------------------------------------------------------------
# MAIN CONTENT
# -----------------------------------------------------------------------------
st.title("Clinical Trial Data Quality & Observability Platform")

runs_df = load_runs_data()

if runs_df.empty:
    st.info("No pipeline executions recorded yet. Click 'Trigger Ingestion Run' in the sidebar to run the pipeline.")
    st.stop()

# Top KPI Metric Cards
latest_run = runs_df.iloc[0]
total_runs_count = len(runs_df)
avg_pass_rate = runs_df["pass_rate_pct"].mean()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Pipeline Runs", f"{total_runs_count}")
with col2:
    st.metric("Latest Status", f"{latest_run['status']}")
with col3:
    st.metric("Latest Pass Rate", f"{latest_run['pass_rate_pct']}%")
with col4:
    st.metric("Latest Rows Loaded", f"{latest_run['records_loaded']:,}")
with col5:
    st.metric("Latest Quarantined", f"{latest_run['records_quarantined']:,}")

st.divider()

# Tabbed Interface
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Pipeline Runs & Trends",
    "🛡️ Quarantine Analysis",
    "🏥 Site & Subject Operations",
    "🧪 Laboratory Data & Safety",
])

# -----------------------------------------------------------------------------
# TAB 1: PIPELINE RUNS & TRENDS
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("Historical Pipeline Executions")

    chart_col1, chart_col2 = st.columns([3, 2])
    with chart_col1:
        # Volume Trend Chart
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(
            x=runs_df["start_time"],
            y=runs_df["records_loaded"],
            name="Clean Records Loaded",
            marker_color="#2E7D32",
        ))
        fig_vol.add_trace(go.Bar(
            x=runs_df["start_time"],
            y=runs_df["records_quarantined"],
            name="Quarantined Records",
            marker_color="#D32F2F",
        ))
        fig_vol.update_layout(
            barmode="stack",
            title="Ingestion Volume by Run (Loaded vs Quarantined)",
            xaxis_title="Run Timestamp",
            yaxis_title="Record Count",
            height=350,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_vol, use_container_width=True)

    with chart_col2:
        # Pass Rate Line Chart
        fig_rate = px.line(
            runs_df,
            x="start_time",
            y="pass_rate_pct",
            markers=True,
            title="Data Quality Pass Rate Trend (%)",
            labels={"start_time": "Timestamp", "pass_rate_pct": "Pass Rate %"},
        )
        fig_rate.update_traces(line_color="#1E88E5", line_width=3)
        fig_rate.update_layout(
            yaxis_range=[0, 105],
            height=350,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    st.subheader("Audit Run Ledger")
    st.dataframe(
        runs_df[[
            "run_id", "start_time", "status", "records_extracted",
            "records_loaded", "records_quarantined", "pass_rate_pct",
            "execution_time_seconds"
        ]],
        use_container_width=True,
    )

# -----------------------------------------------------------------------------
# TAB 2: QUARANTINE ANALYSIS
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Zero-Loss Quarantine Inspection")
    st.caption("Investigate invalid records, root-cause rule violations, and payload details without silent data drops.")

    run_options = ["All Runs"] + runs_df["run_id"].tolist()
    selected_run = st.selectbox("Filter by Pipeline Run ID", run_options)

    quarantine_df = load_quarantine_data(selected_run)

    if quarantine_df.empty:
        st.success("No quarantine records found for the selected run filter!")
    else:
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            # Rule breakdown
            rule_tally = quarantine_df["rule_code"].value_counts().reset_index()
            rule_tally.columns = ["Rule Code", "Violations Count"]
            fig_rules = px.bar(
                rule_tally,
                x="Violations Count",
                y="Rule Code",
                orientation="h",
                title="Quarantine Violations by Rule Code",
                color="Violations Count",
                color_continuous_scale="Reds",
            )
            fig_rules.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_rules, use_container_width=True)

        with q_col2:
            # Entity breakdown
            entity_tally = quarantine_df["source_entity"].value_counts().reset_index()
            entity_tally.columns = ["Source Entity", "Count"]
            fig_pie = px.pie(
                entity_tally,
                values="Count",
                names="Source Entity",
                title="Quarantine Distribution by Source Entity",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_pie.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)

        # Filters
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            entity_filter = st.multiselect(
                "Filter by Entity",
                options=quarantine_df["source_entity"].unique().tolist(),
                default=quarantine_df["source_entity"].unique().tolist(),
            )
        with filter_col2:
            rule_filter = st.multiselect(
                "Filter by Rule Code",
                options=quarantine_df["rule_code"].unique().tolist(),
                default=quarantine_df["rule_code"].unique().tolist(),
            )

        filtered_q = quarantine_df[
            quarantine_df["source_entity"].isin(entity_filter)
            & quarantine_df["rule_code"].isin(rule_filter)
        ]

        st.markdown(f"**Showing {len(filtered_q):,} quarantined records:**")
        st.dataframe(
            filtered_q[[
                "id", "source_entity", "record_identifier", "rule_code",
                "rule_name", "error_message", "quarantined_at"
            ]],
            use_container_width=True,
        )

        # Raw record inspection
        with st.expander("🔍 Inspect Full Raw Record JSON Payload"):
            if not filtered_q.empty:
                selected_record_id = st.selectbox(
                    "Select Quarantine Record ID to view unedited JSON:",
                    filtered_q["id"].tolist(),
                )
                record_row = filtered_q[filtered_q["id"] == selected_record_id].iloc[0]
                st.write(f"**Entity:** {record_row['source_entity']} | **Identifier:** {record_row['record_identifier']} | **Rule:** {record_row['rule_name']}")
                st.info(f"**Diagnostic Error:** {record_row['error_message']}")
                try:
                    parsed_json = json.loads(record_row["raw_record"])
                    st.json(parsed_json)
                except Exception:
                    st.code(record_row["raw_record"], language="json")

# -----------------------------------------------------------------------------
# TAB 3: SITE & SUBJECT OPERATIONS
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Clinical Research Site Performance & Participant Adherence")

    site_df = load_site_metrics()
    if not site_df.empty:
        s_col1, s_col2 = st.columns([3, 2])
        with s_col1:
            fig_sites = px.bar(
                site_df,
                x="site_name",
                y="total_subjects_enrolled",
                color="country",
                title="Participant Enrollment by Clinical Site",
                labels={"site_name": "Site Name", "total_subjects_enrolled": "Enrolled Subjects"},
            )
            fig_sites.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_sites, use_container_width=True)

        with s_col2:
            fig_att = px.bar(
                site_df,
                x="site_id",
                y="visit_attendance_rate_pct",
                title="Visit Attendance Rate by Site (%)",
                color="visit_attendance_rate_pct",
                color_continuous_scale="Blues",
            )
            fig_att.update_layout(yaxis_range=[0, 105], height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_att, use_container_width=True)

        st.markdown("**Site Operational Metrics Summary Table:**")
        st.dataframe(site_df, use_container_width=True)

    st.divider()
    st.subheader("Subject Compliance & Protocol Adherence")
    subj_df = load_subject_metrics()
    if not subj_df.empty:
        st.dataframe(subj_df, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 4: LABORATORY DATA & SAFETY
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("Laboratory Assessments & Safety Biomarkers")

    lab_df = load_lab_data()
    if not lab_df.empty:
        l_col1, l_col2 = st.columns(2)
        with l_col1:
            # Abnormal flag count
            ab_tally = lab_df["abnormal_flag"].value_counts().reset_index()
            ab_tally.columns = ["Safety Flag", "Count"]
            fig_flag = px.pie(
                ab_tally,
                names="Safety Flag",
                values="Count",
                title="Lab Result Flag Distribution",
                hole=0.4,
                color="Safety Flag",
                color_discrete_map={
                    "NORMAL": "#2E7D32",
                    "HIGH": "#F57C00",
                    "LOW": "#1976D2",
                    "CRITICAL": "#D32F2F",
                },
            )
            fig_flag.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_flag, use_container_width=True)

        with l_col2:
            # Distribution of values by test
            fig_box = px.box(
                lab_df,
                x="test_code",
                y="result_value",
                color="test_code",
                title="Biomarker Value Distributions by Test Code",
                labels={"test_code": "Test Code", "result_value": "Measured Value"},
            )
            fig_box.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_box, use_container_width=True)

        st.markdown("**Recent Validated Laboratory Results:**")
        st.dataframe(
            lab_df[[
                "result_id", "visit_id", "subject_id", "test_code", "test_name",
                "result_value", "unit", "reference_low", "reference_high",
                "collection_date", "abnormal_flag"
            ]].head(100),
            use_container_width=True,
        )
