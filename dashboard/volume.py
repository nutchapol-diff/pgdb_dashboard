"""Calendar volume and modality share over existing exam facts."""

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PERIODS = {"Daily": "day", "Weekly": "week", "Monthly": "month"}


def period_start(value, period):
    value = pd.Timestamp(value).date()
    if period == "week":
        return value - timedelta(days=value.weekday())
    if period == "month":
        return value.replace(day=1)
    return value


def next_period(value, period):
    if period == "month":
        return (pd.Timestamp(value) + pd.offsets.MonthBegin(1)).date()
    return value + timedelta(days=7 if period == "week" else 1)


def volume_periods(rows, start, end, period, first_source_day, last_source_day):
    """Fill selected calendar buckets, retaining explicit coverage caveats."""
    records = {pd.Timestamp(row["period_start"]).date(): row for row in rows.to_dict("records")}
    output = []
    current = period_start(start, period)
    while current <= end:
        finish = next_period(current, period) - timedelta(days=1)
        flags = []
        if current < start or finish > end:
            flags.append("Partial selected period")
        if first_source_day is not None and current <= first_source_day <= finish:
            flags.append("First source day in period")
        if last_source_day is not None and current <= last_source_day <= finish:
            flags.append("Latest source day in period")
        row = records.get(current, {})
        output.append({"period_start": current, "period_end": finish,
                       "orders": int(row.get("orders", 0)), "exams": int(row.get("exams", 0)),
                       "coverage": "; ".join(flags) or "Full selected period; source completeness unverified"})
        current = next_period(current, period)
    return pd.DataFrame(output)


def render_volume(query, sql, where, params, start, end, first_day, last_day, chart, panel_title):
    panel_title("Order and Exam Volume", "Bangkok order dates; distinct orders and exam records shown separately.")
    label = st.selectbox("Group volume by", list(PERIODS), key="volume_period")
    period = PERIODS[label]
    rows = query(sql("volume_by_period.sql", where), (period,) + params)
    data = volume_periods(rows, start, end, period, first_day, last_day)
    fig = go.Figure()
    for field, name, color in [("orders", "Distinct orders", "#667fb4"), ("exams", "Exam records", "#207a78")]:
        fig.add_trace(go.Bar(x=data["period_start"], y=data[field], name=name, marker_color=color,
                            customdata=data[["period_end", "coverage"]],
                            hovertemplate="%{x} to %{customdata[0]}<br>%{y:,} " + name + "<br>%{customdata[1]}<extra></extra>"))
    fig.update_layout(barmode="group")
    chart(fig, 315, showlegend=True)
    st.caption("Weeks start Monday. Only selected dates are counted. Canceled orders and deleted exam details are excluded. Empty buckets mean no stored matching records, not proven zero source activity.")
    with st.expander("Period counts and coverage"):
        st.dataframe(data, hide_index=True, width="stretch")


def share_figure(data):
    """Use record counts as slice areas, preserving the selected denominator."""
    displayed = data.head(10).copy()
    if len(data) > 10:
        remaining = int(data.iloc[10:]["exam_records"].sum())
        denominator = int(data["selected_exam_records"].iloc[0])
        displayed = pd.concat([displayed, pd.DataFrame([{"modality_name": "Remaining modalities (combined)", "exam_records": remaining, "selected_exam_records": denominator, "share_pct": 100 * remaining / denominator}])], ignore_index=True)
    fig = go.Figure(go.Pie(labels=displayed["modality_name"], values=displayed["exam_records"],
                          sort=False, textinfo="percent", textposition="inside",
                          marker=dict(colors=["#207a78", "#667fb4", "#d3a247", "#c5605e", "#59a088", "#9c6caa", "#5c96bb", "#bc8555", "#8b9c51", "#bd7394", "#89919a"]),
                          hovertemplate="%{label}<br>%{value:,} exam records<br>%{percent:.2%} of selection<extra></extra>"))
    fig.update_layout(template="plotly_white", height=430, margin=dict(l=10,r=10,t=10,b=10),
                      paper_bgcolor="#faf9f5", font_color="#15233b",
                      legend=dict(itemclick=False, itemdoubleclick=False))
    return fig


def render_share(query, sql, where, params, chart, panel_title):
    panel_title("Modality Share of Exam Records", "Exam count by modality ÷ all selected exam records × 100.")
    data = query(sql("modality_share.sql", where), params)
    if data.empty:
        st.info("No exam records in this filter; share is unavailable.")
        return
    chart(share_figure(data), 430, showlegend=True)
    st.caption(f"Denominator: {int(data['selected_exam_records'].iloc[0]):,} selected exam records. Top ten shown; remaining modalities combined. With one modality selected its share is 100%. Canceled orders, deleted exam details and unmapped rows are excluded.")
    with st.expander("All modality counts and percentages"):
        st.dataframe(data, hide_index=True, width="stretch")
