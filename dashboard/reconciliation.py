"""Shared read-only reconciliation widget for dashboard and Data Explorer."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).parent
DATASETS = {
    "exam": ("RIS_ORDERDTL JOIN RIS_ORDER", "dw.fact_exam + dw.fact_exam_unmapped", "One order detail; invalid required keys/time retained in quarantine", ["sql/sqlserver/source_count_and_max_order.sql", "sql/sqlserver/fact_exam_extract.sql", "sql/postgres/load/count_fact.sql", "sql/postgres/load/count_unmapped.sql"]),
    "ai_result_daily": ("RIS_EXAMRESULTAI", "mart.ai_result_daily", "Creation date / modality / score band", ["sql/sqlserver/ai_result_daily_extract.sql"]),
    "ai_finding_daily": ("RIS_EXAMRESULTAIDTL", "mart.ai_finding_daily", "Parent creation date / modality / finding name", ["sql/sqlserver/ai_finding_daily_extract.sql"]),
    "hl7_ie_daily": ("RIS_HL7IELOG", "mart.hl7_ie_daily", "Creation date / route / type / raw status / ACK / deletion flag", ["sql/sqlserver/hl7_ie_daily_extract.sql"]),
    "hl7_transaction_daily": ("RIS_HL7TRANSACTIONLOG", "mart.hl7_transaction_daily", "Send date / type / partner; null dates preserved", ["sql/sqlserver/hl7_transaction_daily_extract.sql"]),
}


def reconciliation_statement(sql, integration_ready):
    """Keep audits and target counts in the same PostgreSQL statement snapshot."""
    ctes = []
    families = ["exam"] + (["integration"] if integration_ready else [])
    for family in families:
        for kind in ("audit", "counts"):
            statement = sql(f"reconciliation_{family}_{kind}.sql").strip().rstrip(";")
            ctes.append(f"{family}_{kind} AS ({statement})")
    audit_union = " UNION ALL ".join(f"SELECT * FROM {family}_audit" for family in families)
    counts_union = " UNION ALL ".join(f"SELECT * FROM {family}_counts" for family in families)
    ctes.extend([f"audit AS ({audit_union})", f"counts AS ({counts_union})"])
    return "WITH " + ",\n".join(ctes) + """
SELECT a.*, c.stored_rows, c.represented_records,
       c.excluded_records AS excluded_records_current,
       c.undated_records AS undated_records_current
FROM audit a LEFT JOIN counts c USING (dataset)
ORDER BY a.dataset;
"""


def compare_counts(audit, current):
    """Compare recorded load invariants with today's stored representation."""
    result = audit.merge(current, on="dataset", how="left", suffixes=("_audit", "_current"), validate="one_to_one")
    result["load_difference"] = result["source_records"] - result["loaded_records"] - result["excluded_records_audit"]
    result["current_difference"] = result["source_records"] - result["represented_records"] - result["excluded_records_current"]
    result["representation_change"] = result["represented_records"] - result["loaded_records"]
    result["quarantine_change"] = result["excluded_records_current"] - result["excluded_records_audit"]
    result["undated_change"] = result["undated_records_current"] - result["undated_records_audit"]
    def status(row):
        required = [row[key] for key in ("load_difference", "current_difference", "representation_change", "quarantine_change")]
        if any(pd.isna(value) for value in required):
            return "Unavailable"
        if any(value != 0 for value in required):
            return "Mismatch"
        if row["dataset"] != "exam":
            if pd.isna(row["undated_change"]): return "Unavailable"
            if row["undated_change"] != 0: return "Mismatch"
        return "Matched"
    result["check"] = result.apply(status, axis=1)
    return result


def render_reconciliation(query, sql, integration_ready):
    st.subheader("Source-to-target reconciliation")
    st.caption("Full history · date/modality filters do not apply · source counts recorded at load time, target counts read now (cached up to 60 seconds).")
    snapshot = query(reconciliation_statement(sql, integration_ready))
    if snapshot.empty:
        st.info("No completed load audit available.")
        return
    audit = snapshot[["dataset", "source_database", "source_records", "loaded_records", "excluded_records", "undated_records", "finished_at", "consistency_note"]]
    current = snapshot[["dataset", "stored_rows", "represented_records", "excluded_records_current", "undated_records_current"]].rename(columns={"excluded_records_current": "excluded_records", "undated_records_current": "undated_records"})
    if not integration_ready:
        st.info("AI/HL7 reconciliation unavailable: no complete supplementary audit for this source.")
    results = compare_counts(audit, current)
    cols = st.columns(3)
    cols[0].metric("Matched datasets", f"{int(results['check'].eq('Matched').sum())} / {len(results)}")
    cols[1].metric("Mismatched datasets", int(results['check'].eq('Mismatch').sum()))
    cols[2].metric("Checks unavailable", int(results['check'].eq('Unavailable').sum()))
    columns = {"dataset": "Dataset", "check": "Check", "source_records": "Source at load", "loaded_records": "Loaded at audit", "stored_rows": "Stored table rows", "represented_records": "Represented now", "excluded_records_current": "Quarantined now", "undated_records_current": "Undated (included)", "current_difference": "Source minus accounted", "finished_at": "Load finished"}
    st.dataframe(results[list(columns)].rename(columns=columns), hide_index=True, width="stretch")
    st.caption("Matched means count conservation and audit/current coverage agree. It does not prove correct values, join cardinality, or a consistent SQL Server snapshot. Different datasets may have different load times.")
    dataset = st.selectbox("Inspect reconciliation dataset", results["dataset"].tolist(), key="reconciliation_dataset")
    row = results.loc[results["dataset"].eq(dataset)].iloc[0]
    source, target, grain, files = DATASETS[dataset]
    stages, math, code = st.tabs(["Tables and counts", "Try the calculation", "Validation SQL"])
    with stages:
        stage = st.radio("Inspect a stage", ["Source at load", "Stored target", "Excluded / undated", "Validation"], horizontal=True, key="reconciliation_stage")
        if stage == "Source at load":
            st.write(f"**RIS_CU / dbo: {source}**")
            st.write(f"Recorded source records: **{row['source_records']:,}**")
            st.caption(f"Recorded source database: {row['source_database']}. SQL Server is not reread by this widget.")
        elif stage == "Stored target":
            st.write(f"**{target}**")
            st.write(f"Stored table rows: **{row['stored_rows']:,}** · represented source records: **{row['represented_records']:,}**")
            st.caption(grain + ". Aggregate representation uses SUM(event_count), not COUNT(*).")
        elif stage == "Excluded / undated":
            st.write(f"Quarantined: **{row['excluded_records_current']:,}**")
            st.write("Undated: **not measured separately for exam quarantine**" if dataset == "exam" else f"Undated: **{row['undated_records_current']:,}**, already included in represented records.")
            st.caption("Quarantine retains unservable exam rows; it is not a source deletion. Undated integration records are retained but omitted from date-filtered charts. Deleted interface records are included for load reconciliation.")
        else:
            st.write(f"**{row['check']}**")
            st.code("source − represented target − quarantined = difference\nrepresented target − audited loaded = representation change\ncurrent quarantine − audited quarantine = quarantine change\ncurrent undated − audited undated = undated change (integration)", language=None, wrap_lines=True)
            st.dataframe(pd.DataFrame([{key: row[key] for key in ("load_difference", "current_difference", "representation_change", "quarantine_change", "undated_change")}]), hide_index=True, width="stretch")
        fig = go.Figure(go.Bar(x=["Source at load", "Represented now", "Quarantined now"], y=[row["source_records"], row["represented_records"], row["excluded_records_current"]], marker_color=["#667fb4", "#207a78", "#d3a247"]))
        fig.update_layout(template="plotly_white", height=280, margin=dict(l=10,r=10,t=15,b=25), paper_bgcolor="#faf9f5", font_color="#15233b", yaxis_title="Source records")
        st.plotly_chart(fig, width="stretch", theme=None)
        st.caption(str(row["consistency_note"]))
    with math:
        st.info("Illustrative numbers only. Edit values; no database changes are made.")
        examples = st.data_editor(pd.DataFrame({"dataset": ["Exam example", "Aggregate example"], "source records": [100, 100], "represented records": [97, 100], "quarantined": [3, 0], "physical rows": [97, 8], "undated included": [0, 20]}), hide_index=True, key="reconciliation_example")
        examples["difference"] = examples["source records"] - examples["represented records"] - examples["quarantined"]
        examples["count conserved"] = examples["difference"].eq(0)
        st.dataframe(examples, hide_index=True, width="stretch")
        st.caption("100 source events can become 8 aggregate rows and still represent all 100 records. Do not add the 20 undated records again. Zero difference checks conservation only; physical rows are a different grain.")
    with code:
        st.markdown("**Exact combined query: audit and target counts share one PostgreSQL snapshot**")
        st.code(reconciliation_statement(sql, integration_ready), language="sql")
        names = ["reconciliation_exam_audit.sql", "reconciliation_exam_counts.sql"] if dataset == "exam" else ["reconciliation_integration_audit.sql", "reconciliation_integration_counts.sql"]
        for name in names:
            st.markdown(f"**{name}**")
            st.code(sql(name), language="sql")
        source_files = files if dataset == "exam" else ["sql/sqlserver/integration_count.sql", *files, "sql/postgres/load/count_integration_mart.sql", "sql/postgres/load/rollup_integration_stage.sql"]
        for name in source_files:
            with st.expander(name):
                st.code((ROOT / name).read_text(encoding="utf-8"), language="sql")
        st.caption("Source SQL is displayed for review, not executed here. {table} placeholders in loader SQL are resolved from the fixed dataset registry, not user input.")
