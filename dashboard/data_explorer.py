"""Read-only lineage explorer and explicitly illustrative calculation examples."""

from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

from reconciliation import render_reconciliation
from volume import PERIODS, period_start, volume_periods, share_figure
from tat_distribution import tat_box_figure, tat_comparison_figure, tat_group_summary, tat_group_figure
from process_comparisons import COMPARISONS
from stroke import get_stroke_summary
from capture_workflow import render_capture_workflow, LABEL as CAPTURE_LABEL
from population import snapshot_filters
from investigations import render_investigations


ROOT = Path(__file__).parent

# File paths are fixed application metadata, never user-provided identifiers.
FAMILIES = {
    "Exam": {
        "source": "RIS_ORDER + RIS_ORDERDTL + RIS_EXAMRESULT + RIS_TECHWORKS + HR_EMP",
        "transform": "Join order details to order and result; count workflow log rows per accession. Interpret timestamps as Bangkok time. COPY explicit fields; upsert dimensions.",
        "stored": "dw.fact_exam + dw.dim_modality + dw.dim_exam + dw.dim_radiologist",
        "mart": "mart.exam_daily / mart.producer_daily / serving views",
        "files": ["sql/sqlserver/fact_exam_extract.sql", "sql/sqlserver/modalities.sql", "sql/sqlserver/exams.sql", "sql/sqlserver/radiologists.sql", "sql/postgres/load/copy_fact.sql", "sql/postgres/01_schema.sql"],
        "mapping": [("RIS_ORDERDTL.ORDER_ID / EXAM_ID", "fact_exam.order_id / exam_id", "Order-detail keys; order may have several exams"), ("RIS_ORDERDTL.MODALITY_ID → RIS_MODALITY", "fact_exam.modality_id → dim_modality", "Dimension FK; source modality type ID used in filters; device names remain in breakdowns"), ("RIS_MODALITY.MODALITY_TYPE → RIS_MODALITYTYPE.TYPE_ID / TYPE_NAME", "dim_modality.modality_type / modality_type_name", "Filter by source type ID; label from source lookup, no name inference"), ("RIS_ORDERDTL.EXAM_ID → RIS_EXAM", "fact_exam.exam_id → dim_exam", "Dimension FK; exam name used in grouping"), ("RIS_ORDER.ORDER_START_TIME", "fact_exam.ordered_at", "Bangkok datetime → timestamptz"), ("RIS_ORDERDTL.IMAGE_CAPTURED_ON", "fact_exam.image_captured_at", "Preserve missing timestamps"), ("RIS_EXAMRESULT.FIRSTFINALIZED_ON / FINALIZED_ON", "first_finalized_at / finalized_at", "COALESCE first final, then final"), ("RIS_ORDERDTL.IS_DELETED", "fact_exam.is_deleted", "Y=true; N=false; other=null"), ("RIS_TECHWORKS rows per accession", "fact_exam.technical_take_count", "Number of saved workflow entries for the exam; not a repeat-scan or rejected-image count"), ("FINALIZED_BY + HR_EMP", "fact_exam.radiologist_id", "Matched radiologist only")],
    },
    "AI": {
        "source": "RIS_EXAMRESULTAI + RIS_EXAMRESULTAIDTL + RIS_ORDERDTL",
        "transform": "Join finding to parent by EXAM_RESULT_AI_ID; accession lookup supplies modality. Group source pages by creation day and score band or finding name. COPY aggregates, then roll up counts and sums.",
        "stored": "mart.ai_result_daily / mart.ai_finding_daily",
        "mart": "Dashboard GROUP BY and weighted means",
        "files": ["sql/sqlserver/ai_result_daily_extract.sql", "sql/sqlserver/ai_finding_daily_extract.sql", "sql/postgres/load/copy_integration_stage.sql", "sql/postgres/load/rollup_integration_stage.sql", "sql/postgres/02_ai_hl7.sql"],
        "mapping": [("AI header CREATED_ON", "event_day", "CAST as date; parent date for findings"), ("AI header ABNORMALITY_SCORE", "score_bucket + event_count", "Bands include missing and outside 0–1"), ("Finding FINDING_NAME", "finding_name", "Group by catalog label"), ("Finding FINDING_SCORE", "score_sum / score_count / min / max", "Nulls excluded from score denominator; zero valid"), ("Header ACCESSION_NO → detail MODALITY_ID", "modality_id", "LEFT JOIN; unmatched stays in All modality types and Unknown modality type")],
    },
    "HL7": {
        "source": "RIS_HL7IELOG / RIS_HL7TRANSACTIONLOG",
        "transform": "Group interface pages by date, route, raw status/ACK and deletion flag. Group transaction pages with valid delay counts, milliseconds sums and bands. COPY aggregates and roll up.",
        "stored": "mart.hl7_ie_daily / mart.hl7_transaction_daily",
        "mart": "Dashboard sums by date/status/route; weighted valid delay",
        "files": ["sql/sqlserver/hl7_ie_daily_extract.sql", "sql/sqlserver/hl7_transaction_daily_extract.sql", "sql/postgres/load/copy_integration_stage.sql", "sql/postgres/load/rollup_integration_stage.sql", "sql/postgres/02_ai_hl7.sql"],
        "mapping": [("IE CREATED_ON", "event_day", "Log date, not exam order date"), ("SENDER / RECEIVER / MESSAGE_TYPE", "route labels + event_count", "Missing names remain Unknown"), ("STATUS / ACKNOWLEDGMENT_CODE", "status_code / ack_code", "Raw codes; no guessed failure meaning"), ("TRANS_TIMESTAMP / ACK_TIMESTAMP", "valid_delay_count / delay_ms_sum", "Only nonnegative complete pairs"), ("IE IS_DELETED", "is_deleted", "Serving excludes Y; unknown flags remain")],
    },
}

# label: family, serving SQL, filter kind, formula, interpretation
WIDGETS = {
    'Investigation duplicate candidates': ('Exam','investigation_summary.sql','joined','suspected_uncaptured = exam_records - captured_exams only in repeated groups with capture and complete matching keys; what_if_exams = exam_records - suspected_uncaptured. Sum groups by selected rule/date/modality.','Investigation service type 1 only, explicit canceled/deleted records excluded. Suspected duplicates are not confirmed errors. Both matching rules cover the same population; never sum rules.'),
    CAPTURE_LABEL: ("Exam", "capture_workflow_daily.sql", "joined", "For each exam with complete start/end records, calculate earliest start to latest end. Show daily median and 90th percentile in minutes.", "Total recorded workflow time includes gaps between entries. It does not measure repeat scans or the percentage of time a scanner is busy."),
    "STAT stroke candidates: capture / first final >30 min": ("Exam", "stroke_summary.sql", "joined", "Eligible: source clinical instruction LIKE '%stroke%', raw priority S, is_deleted IS FALSE, order is_canceled IS FALSE. Count capture > ordered_at + 30 min and COALESCE(first_final, final) > ordered_at + 30 min separately. Valid denominator: nonnegative, complete timestamp pair; missing/negative endpoints excluded. Exactly 30 min is not a breach.", "Text mentions can include history or suspected stroke; this is a candidate cohort, not a validated acute pathway or SLA. Counts are exam details and may overlap between intervals. This is historical completion time, not current pending age. Separate full-history order metadata is source-checked before use."),
    "Process Time daily stage comparison": ("Exam", "process_time_stages_daily.sql", "fact", "On exams with ordered_at ≤ image_captured_at ≤ report_at: daily mean hours of order→capture and capture→first finalization. Same complete samples for both phases; stacked sum equals mean order→first finalization.", "Selected order dates/type, is_deleted IS FALSE. Complete cohort differs from cards; means are additive only on this shared cohort. Elapsed time includes nights/weekends, not staff working time."),
    "Process Time daily duration bands": ("Exam", "process_time_bands_daily.sql", "fact", "Per order day: count valid order→report intervals in ≤240, >240–1440, >1440–2880, >2880 minutes. Share = 100 × band count / valid interval count.", "Bands partition valid finalized exams. Missing/negative totals are excluded; no completed exams gives no bar. These are descriptive bands, not confirmed SLA targets. Selected type/dates and active exam rules apply."),
    "Process Time priority comparison": ("Exam", "process_time_priority.sql", "fact", "Group by trimmed raw priority code, missing/blank = Unknown. Compute percentile_cont(.5)/60 and percentile_cont(.9)/60 on valid total minutes; also active, valid and missing-report counts.", "No guessed priority meanings or SLA. Small samples may be unstable. Missing reports excluded from percentiles, retained in coverage counts. Selected type/dates and active exam rules apply."),
    "Mean TAT: Normal vs IQR Outliers": ("Exam", "tat_box_daily.sql", "joined", "TAT minutes = (COALESCE(first_finalized_at, finalized_at) − ordered_at) in seconds / 60. Low: TAT < Q1 − 1.5 × IQR. High: TAT > Q3 + 1.5 × IQR. Daily quartiles use all selected valid intervals. Normal: lower fence ≤ TAT ≤ upper fence. For each day and group, mean = SUM(TAT minutes in that group) / COUNT(exams in that group). SQL averages the actual exam durations, not daily means or IQR boundaries.", "Not a four-hour count or SLA. Both tails use the same daily fences as the box plot/comparison. Missing and negative intervals are excluded; deleted/unknown flags are included. A day with no outliers has a NULL mean and no bar. No patient identifiers are returned."),
    "Daily TAT comparison / box plot / IQR outliers / Exams over 4 hours": ("Exam", "tat_box_daily.sql", "joined", "Mean TAT = SUM(valid durations) / COUNT(valid durations). Counts use the left chart axis; mean minutes use the right axis. IQR = Q3 − Q1. Statistical fences = Q1 − 1.5 × IQR and Q3 + 1.5 × IQR. Whiskers are observed values inside fences. Fixed threshold count = valid TAT > 240 minutes.", "Exact daily percentile_cont quartiles for valid order-to-first-final intervals. Includes deleted/unknown flags, matching daily median. Statistical outliers and the 4h prototype threshold have different meanings; neither is a confirmed SLA."),
    "Order and exam volume (Daily / Weekly / Monthly)": ("Exam", "volume_by_period.sql", "volume", "COUNT(DISTINCT order_id) and COUNT(*) within each Bangkok order-date calendar bucket. Weeks start Monday. Missing displayed buckets filled with zero matching stored records.", "Selection boundary periods and first/latest source days are flagged; source completeness is unverified. RIS Snapshot excludes canceled orders and deleted exam details; unknown flags are retained. Orders are counted directly per period, not by summing daily distinct counts."),
    "Modality share of exam records": ("Exam", "modality_share.sql", "joined", "100 × modality exam records / all selected exam records. Group by modality name; denominator follows the same date/modality-type filter.", "Each exam detail contributes to one modality. One selected type may contain multiple modality devices. Includes deleted/unknown rows; unmapped rows excluded. Rounded displayed percentages may not sum to exactly 100%."),
    "Source-to-target reconciliation": ("Validation", "reconciliation_exam_audit.sql", "none", "Source = represented target + quarantined. Compare current target counts and undated coverage with the load audit.", "Full-history check; does not prove value equality or source snapshot consistency."),
    "Snapshot counters / Legacy TECHWORKS entry count": ("Exam", "summary.sql", "fact", "Orders = COUNT(DISTINCT order_id); exams = COUNT(*); captured = count non-null capture; finalized = count non-null COALESCE(first_final, final); legacy multiple-entry metric = count technical_take_count > 1; this is not a repeat-scan count.", "RIS Snapshot excludes canceled orders and deleted exam details; unknown flags are retained. Timestamp presence does not validate an interval. Counts are exam details, not patients or images."),
    "Daily exam records / Median TAT / TAT Outliers": ("Exam", "daily.sql", "joined", "Daily order-date count; p50 of valid (COALESCE(first_final, final) − ordered_at)/60 seconds; outlier count where report > order + 4 hours.", "Includes deleted/unknown rows and all priorities. Missing/negative durations excluded. Exactly 240 minutes is not an outlier."),
    "Top exam definitions": ("Exam", "top_exams.sql", "joined", "COUNT(*) by exam name; largest ten.", "Identically named exam IDs combine. RIS Snapshot excludes canceled orders and deleted exam details; unknown flags are retained."),
    "Orders by Modality": ("Exam", "orders_by_modality_top10.sql", "joined", "COUNT(DISTINCT order_id) within each modality name; largest ten.", "One order can appear in multiple modalities; bar totals can exceed overall distinct orders."),
    "Top Producers": ("Exam", "top_producers.sql", "dates", "SUM(finalized_reports) by display_name over report_date; largest ten.", "Uses report dates and ignores modality. Includes deleted rows; same names can combine providers. Finalizing provider is not necessarily first-final provider."),
    "Process Time cards / >4h share / Timestamp coverage": ("Exam", "process_time_summary.sql", "fact", "For is_deleted IS FALSE: valid phase p50/p90; >4h% = 100 × valid total intervals >240 / all valid total intervals. Coverage flag share uses active exam count.", "Each phase has its own sample. Coverage flags overlap. Unknown deletion flags are excluded too. Capture timing is not patient waiting or active reading."),
    "Process Time daily p50/p90": ("Exam", "process_time_daily.sql", "fact", "Daily p50 and p90 of valid order-to-report minutes for explicitly active rows.", "Grouped by Bangkok order date. Period median is not the average of daily medians."),
    "Process Time by modality": ("Exam", "process_time_by_modality.sql", "fact", "Active counts, valid phase counts, p50/p90 and >4h percentage by modality ID/name.", "Percentiles of phases cannot be added to obtain the total percentile."),
    "AI Result Records / AI Result Activity": ("AI", "ai_activity.sql", "ai", "SUM(event_count) by AI creation day. Card = sum of the displayed day's counts.", "Stored outputs, not distinct exams/patients or successful model runs. No model is run by this app."),
    "AI abnormality score distribution": ("AI", "ai_scores.sql", "ai", "SUM(event_count) per score band: [0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]; missing/outside range separate.", "Bands are descriptive, not clinical thresholds or calibrated probabilities."),
    "Mean AI score by finding / score ranges": ("AI", "ai_findings.sql", "ai", "SUM(score_sum) / SUM(score_count); also record count, scored count, MIN(score_min), MAX(score_max). Top 25 means.", "Weighted across records, not daily means. A finding row is not a positive diagnosis. Source sums use decimal(38,10)."),
    "Daily HL7 log records": ("HL7", "hl7_activity.sql", "dates", "SUM(event_count) per CREATED_ON day and ACK code, excluding IS_DELETED='Y'.", "All routes; modality ignored. Retries/log stages are separate records; blank ACK is not proof of failure."),
    "HL7 status and ACK combinations": ("HL7", "hl7_outcomes.sql", "dates", "SUM(event_count) by raw status and ACK code, excluding deleted interface logs.", "F is not classified as failure. Codes need local interpretation per log type."),
    "HL7 interface routes": ("HL7", "hl7_routes.sql", "dates", "Top 20 sender/receiver/message-type groups; ACK count sums records with nonempty trimmed ACK code.", "Missing route names stay Unknown. FILTER sum may be null when no rows qualify."),
    "HL7 Acknowledgment Delay": ("HL7", "hl7_delays.sql", "dates", "SUM(valid delay milliseconds) / SUM(valid pair count) / 1000; bands ≤1s, >1–5s, >5–30s, >30s.", "Currently all transaction timestamps are missing: no delay is available. Undated rows stay in the mart and audit but not dated charts."),
    "AI / HL7 load coverage": ("HL7", "integration_audit.sql", "none", "Source count = extracted count = SUM(served event counts); report undated counts and last refresh.", "Full-history provenance, not selected-period counts or proof of point-in-time source consistency."),
}

GAPS = {
    "CT Scanner 2 Status": "Need device health/downtime events. Catalog active flags do not establish UP/DOWN.",
    "STAT Strokes >30m": "Stroke candidates exist, but cohort and 30-minute start/end events are unapproved. Deferred backlog.",
    "Unread MRI Queue / Unread Queue by Modality": "Need approved worklist/read-start/unread state. Captured and unfinalized is only a candidate proxy.",
    "Patient Wait Time / Active Patient Wait Times": "Need validated arrival, service start and current waiting state. Order-to-capture is not a substitute.",
    "Prioritized exceptions": "Need incident/escalation and approved stroke/interface rules. Raw statuses do not establish priority.",
    "Scanner Utilization": "Need busy intervals, scheduled available hours and downtime by device.",
    "Radiographer Reject / Repeat Reasons": "Need populated, validated QA reason codes. Workflow log entries do not establish rejection reasons.",
    "Storage Capacity / Volume by Modality": "Need actual used/total archive bytes and study/modality linkage.",
    "PACS Availability": "Need uptime checks and a defined observation window.",
    "HL7 Routing Failures": "Need status/ACK meaning, retry/unique-message identity and delivery rules. Logs alone do not give a validated failure count.",
    "Clinical AI positive / negative findings": "Need vendor/model-specific thresholds. Score rows are not positive diagnoses.",
}


def exam_steps(rows, active_only=False):
    """Mirror timing eligibility for examples and the stored timestamp preview."""
    out = rows.copy()
    report = out["first_final"].combine_first(out["final"])
    active = out["deleted"].eq(False)
    out["eligible row"] = active if active_only else True
    out["chosen report"] = report
    for label, begin, finish in (
        ("order → capture", out["order"], out["capture"]),
        ("capture → report", out["capture"], report),
        ("order → report", out["order"], report),
    ):
        out[label] = (finish - begin).where((finish >= begin) & out["eligible row"])
    return out


def calculation_lab(family, active_only, selection, period="day"):
    st.info("Illustrative inputs only. Edit cells to see the transformations; changes are not saved or sent to a database.")
    count_example = selection in ("Snapshot counters / Legacy TECHWORKS entry count", "Top exam definitions", "Orders by Modality", "Top Producers", "Modality share of exam records")
    if selection == "Order and exam volume (Daily / Weekly / Monthly)":
        st.caption("Synthetic order dates in Bangkok time. This example assumes all rows fall inside the selected date/modality filter.")
        rows = st.data_editor(pd.DataFrame({"order ID": [1, 1, 2, 3], "order date": [pd.Timestamp('2026-09-01').date(), pd.Timestamp('2026-09-01').date(), pd.Timestamp('2026-09-02').date(), pd.Timestamp('2026-10-01').date()]}), hide_index=True, num_rows="dynamic", key="explorer_volume_inputs")
        rows["period start"] = pd.to_datetime(rows["order date"], errors="coerce").map(lambda value: period_start(value, period) if pd.notna(value) else None)
        st.markdown("**After calendar transformation**")
        st.dataframe(rows, hide_index=True, width="stretch")
        st.dataframe(rows.groupby("period start", dropna=False).agg(orders=("order ID", "nunique"), exams=("order ID", "size")).reset_index(), hide_index=True, width="stretch")
        st.caption("Distinct order count is calculated inside each bucket. Multiple exam rows for one order increase exam count without increasing order count.")
    elif count_example:
        st.caption("Synthetic joined order details. One order can have multiple exam rows. Edit an order or modality to see distinct counts change.")
        rows = st.data_editor(pd.DataFrame({"order ID": [1, 1, 2, 3], "exam name": ["Exam A", "Exam B", "Exam A", "Exam A"], "modality": ["CT", "MRI", "CT", "CT"], "captured": [True, True, False, True], "finalized": [True, False, False, True], "workflow log entries": [1, 2, 0, 3], "radiologist": ["Provider A", "", "", "Provider B"]}), key="explorer_count_inputs", hide_index=True, num_rows="dynamic")
        st.markdown("**After aggregation**")
        st.dataframe(pd.DataFrame([{"distinct orders": rows["order ID"].nunique(), "exam records": len(rows), "captured timestamps": int(rows["captured"].sum()), "finalized timestamps": int(rows["finalized"].sum()), "exams with multiple log entries": int((rows["workflow log entries"] > 1).sum())}]), hide_index=True, width="stretch")
        if selection == "Modality share of exam records":
            grouped = rows.groupby("modality", dropna=False).size().rename("exam records").reset_index()
            grouped["selected exam records"] = len(rows)
            grouped["share %"] = 100 * grouped["exam records"] / len(rows) if len(rows) else float("nan")
        elif selection == "Top exam definitions":
            grouped = rows.groupby("exam name", dropna=False).size().rename("exam records").reset_index().sort_values("exam records", ascending=False)
        elif selection == "Top Producers":
            eligible = rows.loc[rows["finalized"] & rows["radiologist"].fillna("").ne("")]
            grouped = eligible.groupby("radiologist").size().rename("finalized exam records").reset_index().sort_values("finalized exam records", ascending=False)
            st.caption("This illustration assumes rows are already within selected report dates; the actual producer SQL ignores modality.")
        else:
            grouped = rows.groupby("modality", dropna=False)["order ID"].nunique().rename("distinct orders").reset_index().sort_values("distinct orders", ascending=False)
            st.caption("An order in both CT and MRI contributes once to each modality, but once overall.")
        st.dataframe(grouped, hide_index=True, width="stretch")
    elif family == "Exam":
        st.caption("Times are minute offsets from an imaginary common start. Blank means missing. Deleted=true is excluded only for Process Time.")
        rows = st.data_editor(pd.DataFrame({"order": [0., 0., 0., 0., 0., 0.], "capture": [5., 10., 20., 30., -5., 10.], "first_final": [10., 20., 40., 80., None, -2.], "final": [15., 25., 45., 90., 300., 120.], "deleted": [False, False, False, False, True, False]}), key="explorer_exam_inputs", hide_index=True, num_rows="dynamic")
        out = exam_steps(rows, active_only)
        st.markdown("**After row transformation** — first-final takes precedence, even if its ordering is invalid.")
        st.dataframe(out, hide_index=True, width="stretch")
        results = []
        for phase in ("order → capture", "capture → report", "order → report"):
            valid = out[phase].dropna()
            results.append({"phase": phase, "valid n": len(valid), "p50 min": valid.quantile(.5) if len(valid) else None, "p90 min": valid.quantile(.9) if len(valid) else None})
        st.markdown("**After aggregation** — linear interpolation matches percentile_cont for these numeric examples.")
        st.dataframe(pd.DataFrame(results), hide_index=True, width="stretch")
        valid = out["order → report"].dropna()
        if selection.startswith("STAT stroke"):
            st.caption("Illustrative timing rows are assumed to belong to noncancelled stroke candidates with priority S. The actual SQL additionally checks membership in the loaded candidate-order table.")
            st.dataframe(pd.DataFrame([{
                "interval": phase, "valid pairs": out[phase].notna().sum(),
                ">30 min": (out[phase].dropna() > 30).sum(),
            } for phase in ("order → capture", "order → report")]), hide_index=True, width="stretch")
        if selection == "Process Time daily stage comparison":
            complete = out.dropna(subset=["order → capture", "capture → report"])
            st.caption("Illustrative rows treated as one order day; both stages use the same complete cohort.")
            st.dataframe(pd.DataFrame([{
                "complete samples": len(complete),
                "order→capture mean hours": complete["order → capture"].mean() / 60,
                "capture→report mean hours": complete["capture → report"].mean() / 60,
                "total mean hours": complete["order → report"].mean() / 60,
            }]), hide_index=True, width="stretch")
        elif selection == "Process Time daily duration bands":
            bands = [("≤4h", valid <= 240), (">4–24h", (valid > 240) & (valid <= 1440)),
                     (">24–48h", (valid > 1440) & (valid <= 2880)), (">48h", valid > 2880)]
            st.dataframe(pd.DataFrame([{"band": label, "exam records": int(mask.sum()),
                                       "share %": 100 * mask.sum() / len(valid) if len(valid) else None}
                                      for label, mask in bands]), hide_index=True, width="stretch")
        breaches = int((valid > 240).sum())
        st.write(f">4h: {breaches} / {len(valid)} valid total intervals" + (f" = {100 * breaches / len(valid):.1f}%" if len(valid) else "; percentage unavailable"))
        if WIDGETS[selection][1] == "tat_box_daily.sql" and len(valid):
            q1, q3 = valid.quantile(.25), valid.quantile(.75)
            lower, upper = q1 - 1.5 * (q3-q1), q3 + 1.5 * (q3-q1)
            inside = valid.between(lower, upper)
            if selection == "Mean TAT: Normal vs IQR Outliers":
                example_outliers = valid.rename("TAT minutes").to_frame()
                example_outliers["side"] = example_outliers["TAT minutes"].map(lambda value: "Low" if value < lower else "High" if value > upper else "Normal")
                st.dataframe(example_outliers, hide_index=True, width="stretch")
                st.dataframe(example_outliers.groupby("side")["TAT minutes"].agg(mean_tat_min="mean", exam_records="size").reset_index(), hide_index=True, width="stretch")
            st.dataframe(pd.DataFrame([{"mean min": valid.mean(), "Q1 min": q1, "Q3 min": q3, "IQR min": q3-q1, "lower cutoff": lower, "upper cutoff": upper, "lower whisker": valid[inside].min(), "upper whisker": valid[inside].max(), "IQR outliers": int((~inside).sum()), "over 4h": breaches}]), hide_index=True, width="stretch")
            st.caption("Treat these illustrative rows as one order day. Values exactly on an IQR fence are inside; exactly 240 minutes is not over 4h.")
        st.caption("This lab explains timestamp math. Snapshot counts, modality counts and provider grouping use the exact SQL shown in the SQL tab.")
    elif family == "AI":
        rows = st.data_editor(pd.DataFrame({"finding": ["Example A"] * 4 + ["Example B"], "score": [.1, .1, .1, .9, None]}), key="explorer_ai_inputs", hide_index=True, num_rows="dynamic")
        st.markdown("**After source aggregation** — retain sums/counts so page boundaries do not distort means.")
        grouped = rows.groupby("finding", dropna=False)["score"].agg(records="size", scored="count", score_sum="sum", minimum="min", maximum="max").reset_index()
        grouped["mean score"] = grouped["score_sum"] / grouped["scored"].replace(0, float("nan"))
        st.dataframe(grouped, hide_index=True, width="stretch")
        def band(value):
            if pd.isna(value): return "Missing"
            if value < 0 or value > 1: return "Outside 0–1"
            return ["[0,.2)", "[.2,.4)", "[.4,.6)", "[.6,.8)", "[.8,1]"][min(int(value * 5), 4)]
        rows["score band"] = rows["score"].map(band)
        st.markdown("**After score binning** — illustrative scores treated as abnormality scores for this separate example.")
        st.dataframe(rows, hide_index=True, width="stretch")
        st.dataframe(rows.groupby("score band", dropna=False).size().rename("result records").reset_index(), hide_index=True, width="stretch")
    else:
        rows = st.data_editor(pd.DataFrame({"status": ["F", "F", "S", "S"], "ACK code": ["AA", "", "AA", ""], "send ms": [0., 0., 0., None], "ACK ms": [500., 3000., -1., None]}), key="explorer_hl7_inputs", hide_index=True, num_rows="dynamic")
        rows["valid delay ms"] = (rows["ACK ms"] - rows["send ms"]).where(rows["ACK ms"] >= rows["send ms"])
        st.markdown("**After row transformation** — raw status preserved; complete nonnegative pairs only.")
        st.dataframe(rows, hide_index=True, width="stretch")
        st.dataframe(rows.groupby(["status", "ACK code"], dropna=False).size().rename("log records").reset_index(), hide_index=True, width="stretch")
        valid = rows["valid delay ms"].dropna()
        st.write(f"Valid pairs: {len(valid)}; mean delay: {valid.sum() / len(valid) / 1000:.3f}s" if len(valid) else "No valid pairs; delay unavailable.")
        st.caption("Synthetic example only: actual CU transaction records currently have no valid timestamp pairs. Interface and transaction examples represent different source tables.")


def render_explorer(query, sql, start, end, modality, fact_where, joined_where, params, ai_where, ai_params, integration_ready, first_day=None, last_day=None, modality_type='All modality types'):
    st.title("Data Explorer")
    st.write("Choose a widget. Follow its tables, inspect stored results, and edit an example to understand the calculation.")
    guide = ROOT / 'widget_guide.html'
    selection = st.selectbox("Widget or calculation", list(WIDGETS) + list(GAPS), key="explorer_widget")
    if guide.exists():
        st.link_button('Open this widget diagram in a new tab', 'http://localhost:8502/#' + quote(selection, safe=''))
        st.caption('Read the table path and column equations at full browser width. Examples are fictional; actual selected data is below.')
    if selection == 'Investigation duplicate candidates':
        render_investigations(query,sql,start,end,modality_type,
            query(sql('source_freshness.sql')).iloc[0]['source_database'],explorer=True)
        return
    if selection in GAPS:
        st.warning("Unavailable — no approved calculation")
        st.write(GAPS[selection])
        st.markdown("**Before:** an appropriate operational source or definition is missing. **After:** no fabricated metric is stored or displayed.")
        return

    if selection == "Source-to-target reconciliation":
        render_reconciliation(query, sql, integration_ready)
        return

    if selection == CAPTURE_LABEL:
        render_capture_workflow(query, sql, joined_where, params,
            query(sql('source_freshness.sql')).iloc[0]['source_database'], explorer=True)
        return

    family, filename, filter_kind, formula, note = WIDGETS[selection]
    if filename in ('summary.sql', 'top_exams.sql', 'volume_by_period.sql', 'modality_share.sql'):
        source_database = query(sql('source_freshness.sql')).iloc[0]['source_database']
        try:
            fact_where, joined_where, cancellation_audit = snapshot_filters(query, source_database, fact_where, joined_where)
        except ValueError as exc:
            st.info(str(exc))
            return
        note = 'RIS Snapshot excludes explicit canceled orders and deleted exam details. Unknown deletion/cancellation is not guessed. Counts are exam details; timestamp presence is not proof of image files.'
        st.markdown('**Population filter:** RIS_ORDER.IS_CANCELED = Y → mart.canceled_orders.order_id. Exclude matching fact_exam.order_id and fact_exam.is_deleted = true (RIS_ORDERDTL.IS_DELETED = Y). Original fact rows are retained.')
        st.code("WHERE f.is_deleted IS NOT TRUE\nAND NOT EXISTS (SELECT 1 FROM mart.canceled_orders c WHERE c.order_id = f.order_id)", language='sql')
        for path in ('sql/sqlserver/canceled_orders.sql', 'sql/postgres/05_canceled_orders.sql'):
            with st.expander(path):
                st.code((ROOT / path).read_text(), language='sql')
    metadata = FAMILIES[family]
    active_only = selection.startswith(("Process Time", "STAT stroke"))
    if filename == "stroke_summary.sql":
        source_database = query(sql("source_freshness.sql")).iloc[0]['source_database']
        stroke, audit = get_stroke_summary(query, sql, joined_where, params, source_database)
        if stroke is None:
            st.info("Stroke-candidate metadata is not loaded for this source.")
            return
        st.caption(f"Candidate flags: {audit['candidate_orders']:,} orders; {audit['examined_orders']:,} source orders examined. Last loaded: {audit['loaded_at']}.")
        st.markdown("**Additional source lineage**: RIS_ORDER.CLINICAL_INSTRUCTION → source LIKE '%stroke%' → mart.stroke_candidate_orders.order_id. RIS_ORDER.IS_CANCELED → is_canceled; raw clinical text is not copied.")
        for path in ('sql/sqlserver/stroke_orders_page.sql', 'sql/postgres/03_stroke_candidates.sql', 'sql/postgres/load/replace_stroke_candidates.sql'):
            with st.expander(path):
                st.code((ROOT / path).read_text(encoding='utf-8'), language='sql')
    st.caption(f"{start} to {end} · {modality} · read-only serving database")
    st.warning(note)
    period = "day"
    if filter_kind == "volume":
        period = PERIODS[st.selectbox("Group volume by", list(PERIODS), key="explorer_volume_period")]
    lineage, stored, lab, code = st.tabs(["1 · Source and transformation", "2 · Stored data", "3 · Calculate", "4 · SQL"])
    with lineage:
        stage = st.radio("Follow the data", ["Before · SQL Server", "Transform · extraction", "After · PostgreSQL", "Serve · widget"], horizontal=True, key="explorer_stage")
        if stage.startswith("Before"):
            st.subheader(metadata["source"])
            st.caption("Source: 10.10.12.97 / RIS_CU / dbo. This page does not connect to or reread SQL Server.")
        elif stage.startswith("Transform"):
            st.write(metadata["transform"])
            st.caption("Exam source uses NOLOCK; supplementary source uses read committed. Neither is guaranteed to be a single consistent source snapshot. Target refreshes roll back on failure.")
        elif stage.startswith("After"):
            st.subheader(metadata["stored"])
            st.write(metadata["mart"])
            st.caption("Exam grain: one order detail. AI/HL7: independent aggregate event grains; do not join their counts directly to facts.")
        else:
            st.subheader(selection)
            st.code(formula, language=None, wrap_lines=True)
        st.markdown("**Column lineage: before and after**")
        st.dataframe(pd.DataFrame(metadata["mapping"], columns=["SQL Server input", "PostgreSQL output", "Transformation"]), hide_index=True, width="stretch")
    if filter_kind == "volume":
        statement, bound = sql(filename, joined_where), (period,) + params
    elif filter_kind == "ai":
        statement, bound = sql(filename, ai_where), ai_params
    elif filter_kind in ("fact", "joined"):
        statement, bound = sql(filename, fact_where if filter_kind == "fact" else joined_where), params
    else:
        statement, bound = sql(filename), (start, end) if filter_kind == "dates" else ()
    with stored:
        st.markdown("**Actual widget query output from PostgreSQL**")
        if family != "Exam" and not integration_ready:
            st.info("Supplementary AI/HL7 marts are not loaded for this source.")
        else:
            result = query(statement, bound)
            if filename in COMPARISONS:
                _, _, figure, samples = COMPARISONS[filename]
                if result.empty or result[samples].sum() == 0:
                    st.info("No valid intervals for this comparison in the selected filter.")
                else:
                    st.plotly_chart(figure(result), width="stretch", theme=None)
            if filename == "tat_box_daily.sql" and not result.empty:
                if selection == "Mean TAT: Normal vs IQR Outliers":
                    outliers = tat_group_summary(result)
                    if outliers.empty:
                        st.info("No low or high IQR outliers in this filter.")
                    else:
                        st.plotly_chart(tat_group_figure(outliers), width="stretch", theme=None)
                        st.dataframe(outliers, hide_index=True, width="stretch")
                else:
                    st.plotly_chart(tat_comparison_figure(result), width="stretch", theme=None)
                    st.plotly_chart(tat_box_figure(result), width="stretch", theme=None)
            if selection == "Modality share of exam records" and not result.empty:
                st.plotly_chart(share_figure(result), width="stretch", theme=None)
                st.caption("Top ten modalities plus remaining modalities combined. Slice areas use exam counts, preserving the full selected denominator.")
                with st.expander("Query rows used for the pie chart"):
                    st.dataframe(result, hide_index=True, width="stretch")
            else:
                st.dataframe(result.head(200), hide_index=True, width="stretch")
            st.caption(f"{len(result):,} result rows; showing up to 200. This is the actual dashboard query, not the illustrative lab.")
            if filter_kind == "volume":
                st.markdown("**Calendar display: empty buckets and coverage labels**")
                st.dataframe(volume_periods(result, start, end, period, first_day, last_day), hide_index=True, width="stretch")
        if family == "Exam":
            with st.expander("Inspect 20 stored exam inputs and row-level timing"):
                st.caption("Actual operational timestamps already copied into dw.fact_exam; not a new source-table read. Sample follows ORDER dates/modality, even for Top Producers, whose result above follows REPORT dates.")
                sample_where = joined_where
                if filename == "stroke_summary.sql":
                    sample_where += " AND f.priority_code='S' AND f.is_deleted IS FALSE AND EXISTS (SELECT 1 FROM mart.stroke_candidate_orders s WHERE s.order_id=f.order_id AND s.is_canceled IS FALSE)"
                sample = query(sql("explorer_exam_sample.sql", sample_where), params)
                st.dataframe(sample, hide_index=True, width="stretch")
                if not sample.empty:
                    renamed = sample.rename(columns={"ordered_at": "order", "image_captured_at": "capture", "first_finalized_at": "first_final", "finalized_at": "final", "is_deleted": "deleted"}).copy()
                    # Convert timezone-aware timestamps to numeric minutes, preserving nulls.
                    for field in ("order", "capture", "first_final", "final"):
                        dates = pd.to_datetime(renamed[field], utc=True)
                        renamed[field] = dates.map(lambda value: value.timestamp() / 60 if pd.notna(value) else float("nan"))
                    steps = exam_steps(renamed, active_only)
                    st.dataframe(steps[["eligible row", "order → capture", "capture → report", "order → report"]], hide_index=True, width="stretch")
                    st.caption("Minutes per sampled row. These 20 rows are not the population used for the widget aggregate.")
        else:
            table = "mart.ai_finding_daily" if filename == "ai_findings.sql" else "mart.ai_result_daily" if family == "AI" else "mart.hl7_transaction_daily" if filename == "hl7_delays.sql" else "mart.integration_load_audit" if filename == "integration_audit.sql" else "mart.hl7_ie_daily"
            with st.expander(f"Inspect stored table: {table}"):
                st.caption("Up to 20 full-history aggregate rows, independent of the date/modality selector. Raw source rows were not retained; use the source SQL and illustrative lab to inspect the before-transform shape.")
                if integration_ready:
                    # The identifier comes exclusively from the fixed table whitelist above.
                    st.dataframe(query(f"SELECT * FROM {table} LIMIT 20"), hide_index=True, width="stretch")
    with lab:
        st.code(formula, language=None, wrap_lines=True)
        calculation_lab(family, active_only, selection, period)
    with code:
        st.markdown("**Exact serving query and bound parameters**")
        st.code(statement, language="sql")
        st.code(repr(bound), language="python")
        st.caption("Parameters are bound by psycopg2. The SQL viewer does not execute arbitrary text.")
        for name in metadata["files"]:
            with st.expander(name):
                st.code((ROOT / name).read_text(encoding="utf-8"), language="sql")
        st.caption("Full-refresh loaders: load.py (exam) and load_ai_hl7.py (supplementary). Source SQL uses pyodbc parameters; target COPY and rollup publish within transactions.")
