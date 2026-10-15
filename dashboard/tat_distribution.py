"""Display daily TAT statistics and anonymous outlier durations."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def tat_group_summary(data):
    """Present database-computed daily means for normal exams and both tails."""
    rows = []
    for row in data.itertuples():
        for mean_column, count_column, category in (
            ("normal_mean_min", "normal_count", "Normal (within IQR fences)"),
            ("low_outlier_mean_min", "low_outlier_count", "Low IQR outliers"),
            ("high_outlier_mean_min", "high_outlier_count", "High IQR outliers"),
        ):
            count = getattr(row, count_column)
            if count:
                rows.append({"order_date": row.order_date, "category": category,
                             "mean_tat_min": float(getattr(row, mean_column)),
                             "exam_records": count})
    return pd.DataFrame(rows, columns=["order_date", "category", "mean_tat_min", "exam_records"])


def tat_group_figure(rows):
    fig = go.Figure()
    for side, color in (("Normal (within IQR fences)", "#207a78"),
                        ("Low IQR outliers", "#5369a7"),
                        ("High IQR outliers", "#c5605e")):
        selected = rows.loc[rows["category"] == side]
        if selected.empty:
            continue
        fig.add_trace(go.Bar(
            x=selected["order_date"], y=selected["mean_tat_min"],
            name=side, marker_color=color,
            customdata=selected[["exam_records"]],
            hovertemplate="%{x}<br>Mean TAT: %{y:,.2f} minutes<br>%{customdata[0]:,} exams<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(template="plotly_white", height=320, barmode="group",
                      margin=dict(l=15, r=15, t=40, b=25),
                      legend=dict(orientation="h", y=1.15, x=0),
                      paper_bgcolor="#faf9f5", font_color="#15233b")
    fig.update_yaxes(title_text="Mean TAT (minutes)", rangemode="tozero")
    fig.update_xaxes(title_text="Bangkok order date")
    return fig


def tat_comparison_figure(data):
    """Counts share the left axis; mean duration uses minutes on the right."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for column, label, color in (
        ("over_four_hours", "Exams over 4 hours", "#d3a247"),
        ("iqr_outliers", "IQR outliers", "#c5605e"),
    ):
        fig.add_trace(go.Scatter(
            x=data["order_date"], y=data[column], name=label,
            mode="lines+markers", line_color=color,
            hovertemplate="%{x}<br>%{y:,} exams<extra>%{fullData.name}</extra>",
        ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data["order_date"], y=data["mean_min"], name="Mean TAT (minutes)",
        mode="lines+markers", line=dict(color="#207a78", dash="dash"),
        hovertemplate="%{x}<br>%{y:,.2f} minutes<extra>%{fullData.name}</extra>",
    ), secondary_y=True)
    fig.update_yaxes(title_text="Exam count", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Mean TAT (minutes)", rangemode="tozero", secondary_y=True)
    fig.update_xaxes(title_text="Bangkok order date")
    fig.update_layout(template="plotly_white", height=360,
                      margin=dict(l=15, r=15, t=45, b=25),
                      legend=dict(orientation="h", y=1.15, x=0),
                      paper_bgcolor="#faf9f5", font_color="#15233b")
    return fig


def tat_box_figure(data):
    fig = go.Figure(go.Box(
        x=data["order_date"], q1=data["q1_min"], median=data["median_min"],
        q3=data["q3_min"], lowerfence=data["lower_whisker_min"],
        upperfence=data["upper_whisker_min"], boxpoints=False,
        name="Daily TAT distribution", marker_color="#207a78",
    ))
    fig.add_hline(y=240, line_dash="dash", line_color="#d3a247",
                  annotation_text="4h prototype threshold", annotation_position="top left")
    fig.update_layout(template="plotly_white", height=360,
                      margin=dict(l=15,r=15,t=30,b=25), showlegend=False,
                      paper_bgcolor="#faf9f5", font_color="#15233b")
    fig.update_yaxes(title_text="Order-to-first-final minutes", rangemode="tozero")
    fig.update_xaxes(title_text="Bangkok order date")
    return fig
