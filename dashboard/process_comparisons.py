"""Comparisons of existing active-exam timing intervals with explicit cohorts."""

import plotly.graph_objects as go
import streamlit as st


def stages_figure(data):
    fig = go.Figure(layout=dict(template="plotly_white"))
    for column, label, color in (
        ('order_capture_mean_hours', 'Order → capture', '#d3a247'),
        ('capture_report_mean_hours', 'Capture → first finalization', '#207a78'),
    ):
        fig.add_trace(go.Bar(x=data.order_date, y=data[column], name=label,
                            marker_color=color, customdata=data[['complete_samples']],
                            hovertemplate='%{x}<br>Mean: %{y:.2f} hours<br>Complete exams: %{customdata[0]:,}<extra>%{fullData.name}</extra>'))
    fig.update_layout(barmode='stack')
    fig.update_yaxes(title_text='Mean elapsed hours', rangemode='tozero')
    fig.update_xaxes(title_text='Bangkok order date')
    return fig


def bands_figure(data):
    fig = go.Figure(layout=dict(template="plotly_white"))
    for column, label, color in (
        ('within_four_hours', '≤4h', '#207a78'),
        ('four_to_24_hours', '>4–24h', '#667fb4'),
        ('hours_24_to_48', '>24–48h', '#d3a247'),
        ('over_48_hours', '>48h', '#c5605e'),
    ):
        fig.add_trace(go.Bar(x=data.order_date, y=100 * data[column] / data.valid_samples,
                            name=label, marker_color=color,
                            customdata=data[[column, 'valid_samples']],
                            hovertemplate='%{x}<br>%{y:.1f}%<br>%{customdata[0]:,} of %{customdata[1]:,} valid exams<extra>%{fullData.name}</extra>'))
    fig.update_layout(barmode='stack')
    fig.update_yaxes(title_text='Share of valid finalized exams (%)', range=[0, 100])
    fig.update_xaxes(title_text='Bangkok order date')
    return fig


def priority_figure(data):
    data = data.loc[data.valid_samples > 0]
    fig = go.Figure(layout=dict(template="plotly_white"))
    for column, label, color in (('p50_hours', 'p50', '#207a78'), ('p90_hours', 'p90', '#d3a247')):
        fig.add_trace(go.Bar(x=data.priority_code, y=data[column], name=label,
                            marker_color=color, customdata=data[['valid_samples', 'active_exams']],
                            hovertemplate='Code: %{x}<br>%{y:.2f} hours<br>%{customdata[0]:,} valid / %{customdata[1]:,} active exams<extra>%{fullData.name}</extra>'))
    fig.update_layout(barmode='group')
    fig.update_yaxes(title_text='Order-to-first-final hours', rangemode='tozero')
    fig.update_xaxes(title_text='Raw RIS priority code', type='category')
    return fig


COMPARISONS = {
    'process_time_stages_daily.sql': (
        'Daily stage comparison',
        'Mean elapsed hours on the same complete cohort; stacked height equals mean order-to-first-final time.',
        stages_figure, 'complete_samples',
    ),
    'process_time_bands_daily.sql': (
        'Daily finalized-exam duration mix',
        'Descriptive elapsed-time bands among valid finalized exams; missing reports are excluded. Hover for counts.',
        bands_figure, 'valid_samples',
    ),
    'process_time_priority.sql': (
        'Timing by priority code',
        'p50/p90 hours by raw RIS code. Code meanings and SLA targets are unverified; hover for sample sizes.',
        priority_figure, 'valid_samples',
    ),
}


def render_process_comparisons(query, sql, where, params, chart, panel_title):
    for filename, (title, description, figure, samples) in COMPARISONS.items():
        with st.container(border=True):
            panel_title(title, description)
            data = query(sql(filename, where), params)
            if data.empty or data[samples].sum() == 0:
                st.info('No valid intervals for this comparison in the selected filter.')
            else:
                chart(figure(data), 320, showlegend=True)
            with st.expander('Calculation rows and sample sizes'):
                st.dataframe(data, hide_index=True, width='stretch')
    st.caption('All comparisons follow selected ORDER dates and modality type and explicitly active exam rows. Elapsed time includes nights/weekends. Completed exams are a subset of all orders; absent final reports do not become zero-minute durations. Small priority samples may be unstable.')
