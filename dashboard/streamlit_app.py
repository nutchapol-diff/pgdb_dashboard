r"""Throwaway Streamlit prototype of the four RadOps reference screens.

Run: .\.venv\Scripts\streamlit.exe run prototypes\radops_star\streamlit_app.py
Reads only from the configured prototype database. Unsupported charts display source gaps.
"""

import html
import os
from datetime import datetime, time, timedelta
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

from data_explorer import render_explorer
from reconciliation import render_reconciliation
from volume import render_volume, render_share
from tat_distribution import tat_box_figure, tat_comparison_figure, tat_group_summary, tat_group_figure
from process_comparisons import render_process_comparisons
from stroke import get_stroke_summary
from capture_workflow import render_capture_workflow
from population import snapshot_filters
from investigations import render_investigations


TZ = ZoneInfo("Asia/Bangkok")
TEAL = "#207a78"
AMBER = "#d3a247"
RED = "#c5605e"
INK = "#15233b"
MUTED = "#69788c"
SQL_DIR = Path(__file__).parent / "sql" / "postgres" / "dashboard"
PG_DATABASE = os.getenv("PGDATABASE", "radops_cu_prototype")


def sql(name, where=None):
    statement = (SQL_DIR / name).read_text(encoding="utf-8")
    return statement.format(where=where) if where is not None else statement

st.set_page_config(page_title="Envision BI · RadOps Prototype", page_icon="🏥", layout="wide")


def pg_password():
    if os.getenv("PGPASSWORD"):
        return os.environ["PGPASSWORD"]
    # Local prototype convenience: reuse the existing Compose setting.
    compose = Path(__file__).resolve().parents[2] / "docker-compose-timescale.yml"
    if compose.exists():
        match = re.search(r"POSTGRES_PASSWORD=([^\s]+)", compose.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    raise RuntimeError("Set PGPASSWORD for the prototype TimescaleDB connection.")


@st.cache_data(ttl=60, show_spinner=False)
def query(sql, params=()):
    with psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "6543"),
        dbname=PG_DATABASE,
        user=os.getenv("PGUSER", "postgres"),
        password=pg_password(),
        connect_timeout=4,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return pd.DataFrame([dict(row) for row in cur.fetchall()])


def esc(value):
    return html.escape(str(value))


def card(label, value, note, tone="teal"):
    st.markdown(
        f'<div class="kpi {tone}"><div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{esc(value)}</div><div class="kpi-note">{esc(note)}</div></div>',
        unsafe_allow_html=True,
    )


def unavailable(title, detail, height=230):
    st.markdown(
        f'<div class="unavailable" style="min-height:{height}px">'
        f'<div class="unavailable-title">{esc(title)}</div>'
        '<div class="unavailable-pill">Unavailable · source needed</div>'
        f'<p>{esc(detail)}</p></div>',
        unsafe_allow_html=True,
    )


def heading(eyebrow, title, description=""):
    st.markdown(
        f'<div class="page-eyebrow">{esc(eyebrow)}</div>'
        f'<h1 class="page-title">{esc(title)}</h1>'
        f'<div class="page-description">{esc(description)}</div>',
        unsafe_allow_html=True,
    )


def panel_title(title, description="", badge=""):
    badge_html = f'<span class="panel-badge">{esc(badge)}</span>' if badge else ""
    st.markdown(
        f'<div class="panel-heading"><div><div class="panel-title">{esc(title)}</div>'
        f'<div class="panel-description">{esc(description)}</div></div>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def chart(fig, height=300, showlegend=False):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=8, r=12, t=12, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial", color=INK, size=12),
        showlegend=showlegend,
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#dfe7e7", tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor="#edf1f0", zeroline=False, tickfont=dict(color=MUTED)),
        hoverlabel=dict(bgcolor="white", font_color=INK),
    )
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def get_bounds():
    row = query(sql("bounds.sql"))
    return tuple(row.iloc[0][key] for key in ("first_day", "last_day", "last_complete_day"))


def filters_where(start, end, modality_type):
    start_at = datetime.combine(start, time.min, TZ)
    end_at = datetime.combine(end + timedelta(days=1), time.min, TZ)
    date_where = "f.ordered_at >= %s AND f.ordered_at < %s"
    params = [start_at, end_at]
    fact_where = date_where
    joined_where = date_where
    if modality_type == "Unknown modality type":
        fact_where += " AND f.modality_id IN (SELECT modality_id FROM dw.dim_modality WHERE modality_type IS NULL)"
        joined_where += " AND m.modality_type IS NULL"
    elif modality_type != "All modality types":
        fact_where += " AND f.modality_id IN (SELECT modality_id FROM dw.dim_modality WHERE modality_type = %s)"
        joined_where += " AND m.modality_type = %s"
        params.append(modality_type)
    return fact_where, joined_where, tuple(params)


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Baskerville:wght@700&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',Arial,sans-serif;color:#15233b}
.stApp{background:#faf9f5}
[data-testid="stHeader"]{background:#faf9f5}
[data-testid="stHeader"] button{color:#15233b}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p,[data-testid="stWidgetLabel"] p{color:#69788c}
[data-testid="stCaptionContainer"]{opacity:1}
[data-testid="stAlertContainer"]{background:#fff1df;color:#806214}
[data-testid="stAlertContentWarning"],[data-testid="stAlertContentWarning"] p{color:#806214}
[data-testid="stTabs"] [role="tab"],[data-testid="stTabs"] [role="tab"] p,
[data-testid="stRadio"] label p,[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p{color:#15233b!important}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e7e9e4;min-width:235px}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#293a51}
[data-testid="stSidebar"] .stRadio label{padding:5px 7px;border-radius:8px}
.block-container{padding-top:4.5rem;padding-bottom:3rem;max-width:1640px}
.brand{font:700 29px/1.2 'Libre Baskerville',Georgia,serif;color:#10213b;margin:13px 0 0}
.brand-sub{font-size:10px;letter-spacing:.18em;font-weight:700;color:#69788c;margin:2px 0 34px}
.side-group{font-size:11px;letter-spacing:.14em;color:#89919b;font-weight:700;margin:22px 0 8px}
.top-line{padding-bottom:13px;border-bottom:1px solid #e6e9e7;margin-bottom:20px}
.freshness{background:#eaf5f2;color:#217b77;border-radius:14px;padding:8px 12px;font-size:12px;font-weight:700;display:inline-block;margin-top:8px}
.freshness.stale{background:#fff1df;color:#926825}
.page-eyebrow{font-size:11px;letter-spacing:.18em;color:#2a797a;font-weight:800;margin:18px 0 8px}
.page-title{font:700 25px/1.3 'Libre Baskerville',Georgia,serif;color:#15233b;margin:0 0 4px}
.page-description{color:#69788c;font-size:14px;margin-bottom:20px}
.kpi{background:#fff;border:1px solid #dfe6e4;border-top:3px solid #2c8b79;border-radius:11px;padding:15px 17px;min-height:121px;box-shadow:0 4px 14px #203c4110}
.kpi.amber{border-top-color:#d3a247}.kpi.red{border-top-color:#c5605e}.kpi.blue{border-top-color:#667fb4}
.kpi.unavailable{border-top-color:#9aa7af;background:#fbfcfc}.kpi.unavailable .kpi-value{font-size:clamp(12px,1.3vw,20px);white-space:nowrap;color:#516175}.kpi.unavailable .kpi-note{color:#68788c}
.kpi-label{font-size:14px;color:#66758a;font-weight:700}.kpi-value{font:700 25px/1.3 'Libre Baskerville',Georgia,serif;color:#15233b;margin:9px 0 3px}.kpi-note{font-size:12px;color:#28765d;font-weight:700}.kpi.amber .kpi-note{color:#a4772e}.kpi.red .kpi-note{color:#b84f51}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border:1px solid #e2e8e5!important;border-radius:12px;box-shadow:0 4px 15px #203c4110;padding:12px}
.panel-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin:2px 1px 12px}.panel-title{font-size:18px;font-weight:800;color:#15233b}.panel-description{font-size:13px;color:#69788c}.panel-badge{border-radius:14px;background:#e7f4f1;color:#247671;padding:5px 8px;font-size:11px;font-weight:800;white-space:nowrap}
.unavailable{background:#fff;border:1px solid #e3e8e5;border-radius:12px;padding:17px;box-shadow:0 4px 15px #203c4110}.unavailable-title{font-weight:800;font-size:18px;margin-bottom:15px}.unavailable-pill{display:inline-block;background:#fff1df;color:#926825;border-radius:20px;padding:5px 10px;font-size:11px;font-weight:800}.unavailable p{color:#69788c;font-size:13px;line-height:1.6;margin-top:15px;max-width:650px}
.footnote{color:#748092;font-size:12px;margin-top:20px}
.data-table{width:100%;border-collapse:collapse;background:#fff;font-size:13px}.data-table th{text-align:left;color:#748092;font-size:11px;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #e5e9e8;padding:10px 6px}.data-table td{padding:10px 6px;border-bottom:1px solid #edf0ef;color:#24364c}.data-table td:last-child,.data-table th:last-child{text-align:right}.data-table tr:last-child td{border-bottom:0}
div[data-testid="stMetric"]{background:white}
[data-testid="stMetricValue"],[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p{color:#15233b!important}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

try:
    first_day, last_day, last_complete_day = get_bounds()
    freshness_rows = query(sql("source_freshness.sql"))
    if first_day is None or freshness_rows.empty:
        heading("RIS_CU · PROTOTYPE", "Source data unavailable", "Target: " + PG_DATABASE)
        st.info("No completed extract is loaded yet. Charts become available after the source load and count validation finish.")
        st.stop()
    freshness = freshness_rows.iloc[0]
    modality_types = query(sql("modalities.sql"))
    modality_labels = {"All modality types": "All modality types"}
    for row in modality_types.itertuples():
        type_id = "Unknown modality type" if pd.isna(row.modality_type) else int(row.modality_type)
        modality_labels[type_id] = row.modality_type_name
    modality_options = list(modality_labels)
except Exception as exc:
    st.error(f"Cannot read {PG_DATABASE}: {exc}")
    st.stop()

with st.sidebar:
    st.markdown('<div class="brand">Envision BI</div><div class="brand-sub">RADIOLOGY OPERATIONS · PROTOTYPE</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-group">OPERATIONS</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", ["Overview", "RIS Snapshot", "Investigation Orders", "Daily Workload", "TAT & Performance", "Process Time", "PACS & IT Health", "Data Validation", "Data Explorer", "Widget Data Flow"], label_visibility="collapsed")
    st.markdown('<div class="side-group">DATA</div>', unsafe_allow_html=True)
    st.caption("Historical RIS snapshot. No live feed is connected.")
    st.caption(f"Source: {freshness['source_database']} · Serving database: {PG_DATABASE}")

top_a, top_b, top_c = st.columns([2.4, 1.3, 1.2], vertical_alignment="bottom")
with top_a:
    st.markdown(f'<div class="top-line"><strong>RADOPS / {esc(freshness["source_database"])}</strong> &nbsp; · &nbsp; Historical operations</div>', unsafe_allow_html=True)
with top_b:
    default_end = last_complete_day or last_day
    default_start = max(first_day, default_end - timedelta(days=6))
    selected_period = st.date_input("Date range", value=(default_start, default_end), min_value=first_day, max_value=last_day)
with top_c:
    modality_type = st.selectbox("Modality type", modality_options, format_func=modality_labels.get)
    modality = modality_labels[modality_type]

if not isinstance(selected_period, (tuple, list)) or len(selected_period) != 2:
    st.info("Select both a start and end date.")
    st.stop()
start, end = selected_period
fact_where, joined_where, params = filters_where(start, end, modality_type)
if page == 'RIS Snapshot':
    unfiltered_fact_where = fact_where
    try:
        fact_where, joined_where, cancel_audit = snapshot_filters(query, freshness['source_database'], fact_where, joined_where)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

order_latest = freshness["source_max_order_at"].astimezone(TZ).strftime("%d %b %Y, %H:%M") if pd.notna(freshness["source_max_order_at"]) else "Unavailable"
result_latest = freshness["source_max_result_at"].astimezone(TZ).strftime("%d %b %Y, %H:%M") if pd.notna(freshness["source_max_result_at"]) else "Unavailable"
st.markdown(
    f'<div class="freshness stale">Historical source · latest order {esc(order_latest)} · latest finalization {esc(result_latest)} (Bangkok)</div>',
    unsafe_allow_html=True,
)

summary = query(sql("summary.sql", fact_where), params).iloc[0]
if freshness["unmapped_exam_count"]:
    st.warning(f"{freshness['unmapped_exam_count']:,.0f} extracted rows lack required order time or keys. They are retained in dw.fact_exam_unmapped and excluded from charts.")

daily = query(sql("daily.sql", joined_where), params)

# AI uses result-created dates and modality; HL7 uses event dates and all routes.
# Existing deployments without the supplementary load retain source-gap cards.
integration_ready = False
ai_activity = pd.DataFrame()
integration_audit = pd.DataFrame()
ai_where = "a.event_day BETWEEN %s AND %s"
ai_params = (start, end)
if modality_type == "Unknown modality type":
    ai_where += " AND m.modality_type IS NULL"
elif modality_type != "All modality types":
    ai_where += " AND m.modality_type = %s"
    ai_params += (modality_type,)
if page in ("Overview", "PACS & IT Health", "Data Validation", "Data Explorer"):
    integration_ready = bool(query("SELECT to_regclass('mart.integration_load_audit') IS NOT NULL AS ready").iloc[0]['ready'])
    if integration_ready:
        integration_audit = query(sql("integration_audit.sql"))
        integration_ready = len(integration_audit) == 4 and bool(
            (integration_audit['source_database'] == freshness['source_database']).all())
    if integration_ready:
        ai_activity = query(sql("ai_activity.sql", ai_where), ai_params)


def ai_activity_chart(height=260):
    panel_title("AI Result Activity", "Stored result records by AI creation date; multiple results may belong to one exam.")
    if ai_activity.empty:
        st.info("No dated AI result records in this filter.")
        return
    fig = go.Figure(go.Bar(x=ai_activity['event_day'], y=ai_activity['result_records'], marker_color=TEAL,
                          hovertemplate="%{x}<br>%{y:,} result records<extra></extra>"))
    chart(fig, height)


def tat_chart():
    panel_title("Median TAT Trend (Order-to-First-Final)", "Daily median; exams without a final timestamp are excluded.", "Minutes")
    if daily.empty or daily["median_tat_min"].isna().all():
        st.info("No finalized exams in this filter.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["order_date"], y=daily["median_tat_min"], mode="lines+markers",
                             line=dict(color=TEAL, width=3), marker=dict(size=7, color="white", line=dict(color=TEAL, width=2)),
                             fill="tozeroy", fillcolor="rgba(32,122,120,.10)", hovertemplate="%{x}<br>%{y:.0f} min<extra></extra>"))
    fig.update_yaxes(title_text="Minutes", rangemode="tozero")
    chart(fig, 275)


if page == "Overview":
    stroke, stroke_audit = get_stroke_summary(query, sql, joined_where, params, freshness['source_database'])
    heading("EXECUTIVE SIGNAL", "Radiology operations at a glance", "Historical RIS extract. Stroke cards show completed intervals for text-based candidates, not a live queue.")
    cols = st.columns(5)
    for col, args in zip(cols, [
        ("CT Scanner 2 Status", "Unavailable", "No scanner downtime events", "unavailable"),
        ("STAT stroke: capture >30 min", "Unavailable" if stroke is None or not stroke['capture_valid'] else f"{stroke['capture_over30']:,}",
         "Candidate data not loaded" if stroke is None else "No recorded capture timing" if not stroke['capture_valid'] else "Order → capture · exam count", "unavailable" if stroke is None or not stroke['capture_valid'] else "amber"),
        ("STAT stroke: first final >30 min", "Unavailable" if stroke is None or not stroke['final_valid'] else f"{stroke['final_over30']:,}",
         "Candidate data not loaded" if stroke is None else "No recorded report timing" if not stroke['final_valid'] else "Order → first final · exam count", "unavailable" if stroke is None or not stroke['final_valid'] else "amber"),
        ("Unread MRI Queue", "Unavailable", "RIS worklist semantics unverified", "unavailable"),
        ("Patient Wait Time (Avg)", "Unavailable", "Arrival and service-start semantics unverified", "unavailable"),
    ]):
        with col: card(*args)
    if stroke is not None:
        st.caption("Historical exam counts using recorded timings. Stroke candidates are identified by clinical text and priority S; the acute stroke pathway remains unconfirmed. Calculation and coverage details are in Data Explorer.")
    st.write("")
    left, right = st.columns([1.65, 1])
    with left:
        with st.container(border=True): tat_chart()
    with right:
        unavailable("Prioritized exceptions", "Needs scanner incident, STAT stroke cohort, and interface escalation feeds. RIS alone cannot reproduce the example alerts.", 363)
    st.write("")
    left, right = st.columns([1.65, 1])
    with left:
        unavailable("Scanner utilization", "Requires scheduled capacity, scanner activity intervals, and downtime telemetry by device.", 210)
    with right:
        if integration_ready:
            with st.container(border=True): ai_activity_chart(210)
        else:
            unavailable("AI insights preview", "AI result aggregates have not been loaded for this source.", 210)

elif page == "RIS Snapshot":
    heading("HISTORICAL RIS ACTIVITY", "What the current extract can measure", "Observed order and exam records in the selected period.")
    st.caption("Canceled orders (RIS_ORDER.IS_CANCELED = Y) and deleted exam details (RIS_ORDERDTL.IS_DELETED = Y) are excluded. Image captured means a capture timestamp is present; remaining exams may still have no recorded capture.")
    before = query(sql('summary.sql', unfiltered_fact_where), params).iloc[0]
    st.caption(f"Excluded {before['exams'] - summary['exams']:,.0f} exam records. Exam–image gap: {before['exams'] - before['captured_exams']:,.0f} before → {summary['exams'] - summary['captured_exams']:,.0f} after exclusions. Cancellation metadata refreshed {cancel_audit.iloc[0]['loaded_at'].astimezone(TZ):%d %b %Y, %H:%M} (Bangkok).")
    cols = st.columns(4)
    for col, args in zip(cols, [
        ("Distinct orders", f"{summary['orders']:,.0f}", "Unique RIS order IDs", "teal"),
        ("Exam records", f"{summary['exams']:,.0f}", "Extracted order details", "blue"),
        ("Image captured", f"{summary['captured_exams']:,.0f}", "Capture timestamp present", "teal"),
        ("Report finalized", f"{summary['finalized_exams']:,.0f}", "Final timestamp present", "teal"),
    ]):
        with col: card(*args)
    st.write("")
    left, right = st.columns([1.2, 1])
    with left:
        with st.container(border=True):
            render_volume(query, sql, joined_where, params, start, end,
                          first_day, last_day, chart, panel_title)
    with right:
        with st.container(border=True):
            panel_title("Top Exam Names", "Most common exam definitions in this filter.")
            top_exams = query(sql("top_exams.sql", joined_where), params)
            if top_exams.empty:
                st.info("No exam records in this filter.")
            else:
                st.dataframe(top_exams, hide_index=True, width="stretch", height=315)

    with st.container(border=True):
        render_share(query, sql, joined_where, params, chart, panel_title)

elif page == 'Investigation Orders':
    heading('INVESTIGATION ORDERS','Investigation registrations and capture','Compare Investigation exam records and suspected extra registrations.')
    render_investigations(query,sql,start,end,modality_type,freshness['source_database'])

elif page == "Daily Workload":
    heading("DAILY OPERATIONS", "Daily workload and bottlenecks", "Historical order activity from RIS.")
    left, right = st.columns([1.1, 1])
    with left:
        unavailable("Active Patient Wait Times by Modality", "Requires validated arrival, service-start, and current waiting-state data from this site. Image capture is not a validated service-start event.", 330)
    with right:
        unavailable("Scanner Utilization", "RIS modality assignment is available, but planned scanner hours and actual uptime are not.", 330)
    st.write("")
    left, right = st.columns([1.1, 1])
    with left:
        with st.container(border=True):
            panel_title("Orders by Modality", "Distinct orders in the selected period; an order may span modalities.")
            modality_counts = query(sql("orders_by_modality_top10.sql", joined_where), params)
            fig = go.Figure(go.Bar(x=modality_counts["order_count"], y=modality_counts["modality_name"],
                                   orientation="h", marker_color=TEAL, hovertemplate="%{y}: %{x:,} orders<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            chart(fig, 340)
    with right:
        unavailable("Unread Queue by Modality", "Captured/unfinalized records alone do not establish an unread queue. A validated RIS worklist state and rules for deleted or read-started exams are required.", 380)

elif page == "TAT & Performance":
    heading("SERVICE PERFORMANCE", "Turnaround performance in context", "Order-to-first-final is the prototype TAT definition.")
    distribution = query(sql("tat_box_daily.sql", joined_where), params)
    outlier_rows = tat_group_summary(distribution)
    left, right = st.columns(2)
    with left:
        with st.container(border=True): tat_chart()
    with right:
        with st.container(border=True):
            panel_title("Mean TAT: Normal vs IQR Outliers", "Daily mean minutes: normal exams beside low and high IQR outliers.")
            if distribution.empty:
                st.info("No valid finalized exam intervals in this filter.")
            elif outlier_rows.empty:
                st.info("No low or high IQR outliers in this filter.")
            else:
                chart(tat_group_figure(outlier_rows), 320, showlegend=True)
                st.caption("Mean = total TAT minutes ÷ exam count in each daily group. Normal includes durations within both IQR fences, including the boundaries; it does not imply meeting an SLA. Hover for counts. Empty groups have no bar.")
                with st.expander("Daily group means and counts"):
                    st.dataframe(outlier_rows, hide_index=True, width="stretch")
    with st.container(border=True):
        panel_title("Daily TAT Comparison", "Three lines: exams over four hours, IQR outliers and mean TAT.")
        if distribution.empty:
            st.info("No valid finalized exam intervals in this filter.")
        else:
            chart(tat_comparison_figure(distribution), 360, showlegend=True)
            st.caption("Left axis: exam counts. Right axis: arithmetic mean TAT in minutes (sum of valid durations ÷ valid exams). Counts can overlap; line heights across axes are not directly comparable. Four hours is a prototype threshold, not a confirmed SLA.")
    with st.container(border=True):
        panel_title("Daily TAT Box Plot", "Box: middle 50% of valid durations. Whiskers: observed values within 1.5 × IQR fences.")
        if distribution.empty:
            st.info("No valid finalized exam intervals in this filter.")
        else:
            chart(tat_box_figure(distribution), 360)
            st.caption("Statistical outliers fall below Q1 − 1.5 × IQR or above Q3 + 1.5 × IQR. Outlier points are omitted; exact counts and cutoffs are in the table. Includes deleted/unknown flags, matching the daily median.")
            with st.expander("Quartiles, whiskers and both outlier counts"):
                st.dataframe(distribution, hide_index=True, width="stretch")
    st.write("")
    left, right = st.columns(2)
    with left:
        unavailable("Radiographer Reject / Repeat Reasons", "TECHWORKS records capture workflow timing. Its row count does not identify rejected or repeated scans; a coded rejection source is needed.", 290)
    with right:
        with st.container(border=True):
            panel_title("Top Producers", "Finalized reports dated within the selected range.", "Reports")
            producers = query(sql("top_producers.sql"), (start, end))
            rows = "".join(
                f"<tr><td>{esc(row['Radiologist'])}</td><td>{int(row['Reports']):,}</td></tr>"
                for _, row in producers.iterrows()
            )
            st.markdown(
                '<table class="data-table"><thead><tr><th>Radiologist</th><th>Reports</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True,
            )
    st.write("")
    st.caption("Capture workflow timing from TECHWORKS is available on Process Time. Log entries are not repeat-scan counts.")

elif page == "Process Time":
    heading("PROCESS TIME", "Exam journey from order to report",
            "Historical RIS timestamps for active (not soft-deleted) exam records. Each phase uses its own valid sample.")
    timing = query(sql("process_time_summary.sql", fact_where), params).iloc[0]
    st.caption(f"{summary['exams'] - timing['exams']:,} soft-deleted exam records excluded from this selection.")

    def minutes(value):
        return "—" if pd.isna(value) else f"{value:,.1f} min"

    cols = st.columns(4)
    for col, args in zip(cols, [
        ("Order → capture", minutes(timing["capture_p50"]),
         f"p90 {minutes(timing['capture_p90'])} · n={timing['capture_samples']:,}", "teal"),
        ("Capture → report", minutes(timing["reading_p50"]),
         f"p90 {minutes(timing['reading_p90'])} · n={timing['report_after_capture_samples']:,}", "blue"),
        ("Order → report", minutes(timing["total_p50"]),
         f"p90 {minutes(timing['total_p90'])} · n={timing['total_samples']:,}", "teal"),
        ("Over four hours", "—" if pd.isna(timing["over_four_hours_pct"]) else f"{timing['over_four_hours_pct']:.1f}%",
         f"{timing['over_four_hours']:,} of {timing['total_samples']:,} valid order → report", "amber"),
    ]):
        with col: card(*args)

    st.write("")
    with st.container(border=True):
        panel_title("Daily order-to-report distribution", "Median (p50) and 90th percentile (p90) by Bangkok order date; includes valid samples only.")
        timing_daily = query(sql("process_time_daily.sql", fact_where), params)
        if timing_daily.empty or timing_daily["valid_samples"].sum() == 0:
            st.info("No valid order-to-report intervals in this filter.")
        else:
            fig = go.Figure()
            for field, name, color in [("p50_min", "p50", TEAL), ("p90_min", "p90", AMBER)]:
                fig.add_trace(go.Scatter(x=timing_daily["order_date"], y=timing_daily[field],
                                         mode="lines+markers", name=name, line=dict(color=color, width=3),
                                         customdata=timing_daily["valid_samples"],
                                         hovertemplate="%{x}<br>" + name + ": %{y:.1f} min<br>n=%{customdata:,}<extra></extra>"))
            fig.update_yaxes(title_text="Minutes", rangemode="tozero")
            chart(fig, 310, showlegend=True)

    st.write("")
    with st.container(border=True):
        panel_title("Process time by modality", "Minutes and valid sample counts for each phase; >4h uses valid order-to-report exams.")
        by_modality = query(sql("process_time_by_modality.sql", joined_where), params)
        if by_modality.empty:
            st.info("No active exams in this filter.")
        else:
            st.dataframe(by_modality, hide_index=True, width="stretch", height=390)

    render_process_comparisons(query, sql, fact_where, params, chart, panel_title)
    with st.container(border=True):
        render_capture_workflow(query, sql, joined_where, params, freshness['source_database'])

    with st.container(border=True):
        panel_title("STAT stroke candidates: both 30-minute intervals", "Historical completed intervals, selected order dates and modality type; source priority S and stroke-text mentions.")
        stroke, stroke_audit = get_stroke_summary(query, sql, joined_where, params, freshness['source_database'])
        if stroke is None:
            st.info("Stroke-candidate metadata is not loaded for this source.")
        else:
            rows = []
            for label, prefix in (("Order → capture", "capture"), ("Order → first finalization", "final")):
                n = stroke[prefix + '_valid']
                rows.append({'Interval': label, 'Eligible candidate exams': stroke['eligible_exams'],
                             'Valid pairs': n, '>30 min exams': stroke[prefix + '_over30'] if n else None,
                             '>30 min share (%)': 100 * stroke[prefix + '_over30'] / n if n else None,
                             'Missing endpoint': stroke[prefix + '_missing'], 'Negative pairs': stroke[prefix + '_invalid']})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("Same eligible cohort; each interval has its own valid denominator. An exam can breach both, so counts must not be added. Source text is a candidate rule, not a confirmed acute stroke pathway. Missing endpoints are not completed breaches.")

    st.write("")
    with st.container(border=True):
        panel_title("Timestamp coverage and ordering", "Counts among active exams in the selected period.")
        quality = pd.DataFrame([
            {"Check": "Active exam records", "Count": timing["exams"]},
            {"Check": "Missing image capture", "Count": timing["missing_capture"]},
            {"Check": "Missing final report", "Count": timing["missing_report"]},
            {"Check": "Capture before order", "Count": timing["capture_before_order"]},
            {"Check": "Report before capture", "Count": timing["report_before_capture"]},
            {"Check": "Report before order", "Count": timing["report_before_order"]},
        ])
        quality["Share of exams"] = quality["Count"].apply(
            lambda count: f"{100 * count / timing['exams']:.1f}%" if timing["exams"] else "—")
        st.dataframe(quality, hide_index=True, width="stretch")
        st.caption("Order → capture is workflow time, not patient waiting time. Capture → report is a timestamp interval, not a validated reading duration. Negative intervals are excluded from the affected measure.")

elif page == "PACS & IT Health":
    heading("INFRASTRUCTURE HEALTH", "AI results and HL7 integration", "AI creation dates and HL7 event dates; historical records from RIS_CU.")
    ai_total = int(ai_activity['result_records'].sum()) if not ai_activity.empty else 0
    cols = st.columns(4)
    for col, args in zip(cols, [
        ("Current Storage Capacity", "Unavailable", "PACS telemetry needed", "amber"),
        ("HL7 Routing Failures", "Unavailable", "Failure classification unverified", "amber"),
        ("AI Result Records", f"{ai_total:,}" if integration_ready else "Unavailable",
         "Stored results in selected dates/modality" if integration_ready else "AI aggregates not loaded", "teal"),
        ("PACS Availability", "Unavailable", "Uptime telemetry needed", "amber"),
    ]):
        with col: card(*args)
    st.write("")
    left, right = st.columns(2)
    with left:
        unavailable("Storage Volume by Modality", "Need PACS storage measurements linked to study modality and time.", 265)
    with right:
        if integration_ready:
            with st.container(border=True): ai_activity_chart(265)
        else:
            unavailable("AI Triage Findings", "AI result aggregates have not been loaded for this source.", 265)
    st.write("")
    if not integration_ready:
        unavailable("Integration data", "Run load_ai_hl7.py for this source to publish AI and HL7 aggregates.", 215)
    else:
        st.caption("AI records include results linked to deleted exam details. Unmatched modality records appear under All modality types or Unknown modality type. Scores are model outputs, not confirmed diagnoses; positive/negative thresholds are unverified.")
        with st.container(border=True):
            panel_title("AI Abnormality Score Distribution", "Result records in fixed score bands; no clinical threshold is applied.")
            scores = query(sql("ai_scores.sql", ai_where), ai_params)
            if scores.empty:
                st.info("No AI scores in this filter.")
            else:
                chart(go.Figure(go.Bar(x=scores['score_bucket'], y=scores['result_records'], marker_color=TEAL)), 280)
        with st.container(border=True):
            panel_title("Mean AI Score by Finding", "Top 25 by mean score; each mean uses all scored records for that finding.")
            findings = query(sql("ai_findings.sql", ai_where), ai_params)
            if findings.empty:
                st.info("No AI finding records in this filter.")
            else:
                fig = go.Figure(go.Bar(x=findings['mean_score'], y=findings['finding_name'], orientation='h', marker_color=TEAL,
                                      customdata=findings['scored_records'], hovertemplate="%{y}<br>Mean %{x:.4f}<br>n=%{customdata:,}<extra></extra>"))
                fig.update_yaxes(autorange='reversed')
                fig.update_xaxes(title_text='Mean model score')
                chart(fig, 480)
        if not findings.empty:
            with st.expander("Finding score ranges and sample counts"):
                st.dataframe(findings, hide_index=True, width='stretch')

        st.subheader("HL7 outcomes as recorded")
        st.caption("HL7 charts use all routes and ignore the modality selector. Soft-deleted logs are excluded. Log records are not unique messages; retries may appear more than once. Blank ACK codes do not prove failure, and status F is not classified as failure.")
        hl7 = query(sql("hl7_activity.sql"), (start, end))
        outcomes = query(sql("hl7_outcomes.sql"), (start, end))
        with st.container(border=True):
            panel_title("Daily HL7 Log Records", "Grouped by recorded acknowledgment code and log creation date.")
            if hl7.empty:
                st.info("No dated HL7 interface logs in this range.")
            else:
                fig = go.Figure()
                for code, rows in hl7.groupby('ack_code'):
                    fig.add_trace(go.Bar(x=rows['event_day'], y=rows['log_records'], name=str(code)))
                fig.update_layout(barmode='stack')
                chart(fig, 300, showlegend=True)
        with st.container(border=True):
            panel_title("Status and Acknowledgment Codes", "Raw source codes; vendor workflow status meanings are not inferred.")
            if outcomes.empty:
                st.info("No outcomes in this date range.")
            else:
                fig = go.Figure()
                for code, rows in outcomes.groupby('ack_code'):
                    fig.add_trace(go.Bar(x=rows['status_code'], y=rows['log_records'], name=str(code)))
                fig.update_layout(barmode='stack')
                fig.update_xaxes(title_text='Source STATUS code')
                chart(fig, 300, showlegend=True)
        with st.container(border=True):
            panel_title("HL7 Routes", "Top 20 sender/receiver/message-type combinations by log records.")
            st.dataframe(query(sql("hl7_routes.sql"), (start, end)), hide_index=True, width='stretch')
            st.caption("Unknown sender/receiver means route names are absent in the source. Those records still contribute to message-type counts.")

        delays = query(sql("hl7_delays.sql"), (start, end))
        valid_delay_count = int(delays['valid_delay_records'].sum()) if not delays.empty else 0
        transaction_audit = integration_audit.loc[integration_audit['dataset'] == 'hl7_transaction_daily'].iloc[0]
        if not valid_delay_count:
            unavailable("HL7 Acknowledgment Delay", "No valid send/ACK timestamp pairs in the selected range. "
                        f"Full extract: {int(transaction_audit['undated_rows']):,} of {int(transaction_audit['loaded_rows']):,} transaction records lack a send date. "
                        "Missing timestamps cannot be treated as zero delay or failed delivery.", 170)
        else:
            left, right = st.columns(2)
            with left:
                with st.container(border=True):
                    panel_title("Mean Acknowledgment Delay", "Seconds from TRANS_TIMESTAMP to ACK_TIMESTAMP; valid nonnegative pairs only.")
                    chart(go.Figure(go.Scatter(x=delays['event_day'], y=delays['mean_delay_seconds'], mode='lines+markers', line=dict(color=TEAL))), 280)
            with right:
                with st.container(border=True):
                    panel_title("Acknowledgment Delay Distribution", "Exact delay bands; records lacking timestamps and negative intervals are excluded.")
                    values = [int(delays[key].sum()) for key in ('delay_le_1s','delay_1_5s','delay_5_30s','delay_gt_30s')]
                    chart(go.Figure(go.Bar(x=['0–1s','>1–5s','>5–30s','>30s'], y=values, marker_color=AMBER)), 280)
            st.dataframe(delays, hide_index=True, width='stretch')
        with st.expander("AI / HL7 load coverage and provenance"):
            st.dataframe(integration_audit, hide_index=True, width='stretch')
            st.caption("Undated records are retained in the marts but excluded from date-filtered charts. Full histories were extracted in primary-key pages; source snapshot isolation is disabled, so this is not a guaranteed point-in-time source snapshot.")

elif page == "Data Validation":
    heading("DATA VALIDATION", "Transformation reconciliation",
            "Recorded source counts compared with the current full-history serving data.")
    render_reconciliation(query, sql, integration_ready)

elif page == "Data Explorer":
    render_explorer(query, sql, start, end, modality, fact_where, joined_where,
                    params, ai_where, ai_params, integration_ready, first_day, last_day, modality_type)

elif page == "Widget Data Flow":
    heading('DATA EXPLAINED', 'How the dashboard gets its numbers',
            'A visual explanation of source fields, transformations, storage and calculations. Teaching examples are fictional and do not follow the date/modality filters above.')
    guide = Path(__file__).parent / 'widget_guide.html'
    if guide.exists():
        st.link_button('Open diagram in a new tab', 'http://localhost:8502/', type='primary')
        st.caption('The diagram opens at full browser width with its own widget selector. Click a table or widget to inspect its SQL and column equations.')
    else:
        st.info('Generate widget_guide.html with build_widget_guide.py to view the widget data-flow diagram.')

st.markdown(
    '<div class="footnote">Prototype · read-only TimescaleDB mart and exam fact · '
    'no patient identifiers or report content · unavailable means no verified source</div>',
    unsafe_allow_html=True,
)
