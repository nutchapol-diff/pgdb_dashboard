"""Explain and compare investigation registration matching; never confirm duplicates."""
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).parent
LABEL='Investigation duplicate candidates'
RULES={'Same patient + visit + day + exam':'same_visit',
       'Same patient + day + exam (across visits)':'same_day'}


def render_investigations(query,sql,start,end,modality_type,source_database,explorer=False):
    st.subheader(LABEL)
    ready=query("SELECT to_regclass('mart.investigation_group_load_audit') IS NOT NULL AND EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('mart.investigation_groups') AND attname='definition_service_exams' AND NOT attisdropped) AS ready").iloc[0]['ready']
    audit=query('SELECT * FROM mart.investigation_group_load_audit') if ready else None
    if audit is None or audit.empty or audit.iloc[0]['source_database']!=source_database:
        st.info('Investigation groups are unavailable for this source. Run load_investigation_groups.py.')
        return
    st.caption("Investigation services only: order-detail SERVICE_TYPE = 1, or exam-definition SERVICE_TYPE = '1' when the detail value is missing. Explicit canceled orders and deleted exam details are excluded at extraction.")
    rule_label=st.radio('Match registrations using',list(RULES),key='investigation_match_rule')
    rule=RULES[rule_label]
    st.warning('Suspected duplicates only. A repeated exam may be intentional. What-if counts illustrate the effect of the rule; they are not confirmed unique investigations.')
    st.caption('Both rules also require the same source organization and modality device. Missing patient identity is never matched. The same-visit rule also requires a recorded visit number.')
    where='f.match_rule = %s AND f.order_day BETWEEN %s AND %s'
    params=[rule,start,end]
    if modality_type=='Unknown modality type':
        where+=' AND m.modality_type IS NULL'
    elif modality_type!='All modality types':
        where+=' AND m.modality_type = %s'
        params.append(modality_type)
    params=tuple(params)
    summary=query(sql('investigation_summary.sql',where),params).iloc[0]
    st.caption(f"Service classification: {summary['detail_service_exams']:,.0f} exam records use the order-detail service type; {summary['definition_service_exams']:,.0f} use the exam-definition fallback.")
    if summary['definition_service_exams']:
        st.caption('Fallback uses the current exam definition; historical service classification is unavailable when the order detail did not record it.')
    columns=st.columns(4)
    for col,label,field in zip(columns,['Recorded investigation exams','Exams with capture timestamp','Suspected extra registrations','What-if exam count'],
                               ['exam_records','captured_exams','suspected_uncaptured','what_if_exams']):
        col.metric(label,f"{summary[field]:,.0f}")
    before=summary['exam_records']-summary['captured_exams']
    after=summary['what_if_exams']-summary['captured_exams']
    st.markdown(f"**Exam–capture gap:** {before:,.0f} recorded → **{after:,.0f} in the what-if scenario**. Capture counts stay unchanged.")
    rows=query(sql('investigation_daily.sql',where),params)
    if rows.empty:
        st.info('No Investigation exam records in this selection.')
    else:
        fig=go.Figure()
        for field,label,color in [('exam_records','Recorded investigation exams','#667fb4'),
                                  ('what_if_exams','What-if exams (suspects subtracted)','#d3a247'),
                                  ('captured_exams','Exams with capture timestamp','#207a78')]:
            fig.add_trace(go.Bar(x=rows['order_day'],y=rows[field],name=label,marker_color=color,
                hovertemplate='%{x|%d %b %Y}<br>'+label+': %{y:,} exam records<extra></extra>'))
        fig.update_layout(template='plotly_white',barmode='group',height=400,
            font={'color':'#15233b'},paper_bgcolor='white',plot_bgcolor='white',
            xaxis_title='Order date (Bangkok time)',yaxis_title='Exam records (count)',
            legend={'orientation':'h','y':1.2},margin={'t':90,'b':60})
        st.plotly_chart(fig,width='stretch',theme=None)
        with st.expander('Daily counts behind the chart'):
            st.dataframe(rows,hide_index=True,width='stretch')
    st.markdown('**Candidate groups — up to 50**')
    samples=query(sql('investigation_candidates.sql',where),params)
    if samples.empty:
        st.info('No uncaptured registrations match a captured exam under this rule.')
    else:
        st.dataframe(samples,hide_index=True,width='stretch')
    st.caption(f"{summary['candidate_groups']:,.0f} candidate groups. {summary['unmatchable_exams']:,.0f} exam records lack matching keys; {summary['repeated_without_capture']:,.0f} exam records are in repeated groups with no capture. These records remain in the what-if count.")
    with st.expander('Source → transformed table → calculation',expanded=explorer):
        st.markdown('**SQL Server:** RIS_ORDER supplies patient/visit, organization and order date; RIS_ORDERDTL supplies exam, modality, service type and capture timestamp. RIS_EXAM supplies fallback service classification; RIS_SERVICETYPE confirms Investigation.')
        st.markdown('**Transform:** exclude canceled/deleted records and non-Investigation services; group by the selected matching rule plus exam, modality and organization. Patient and visit identities are used only within SQL Server and are not copied.')
        st.markdown('**Stored:** `mart.investigation_groups` keeps group date, minimum source order ID as an internal anchor, exam/modality IDs, record counts, captured counts and suspect counts. Each rule covers the same eligible population; never add the two rules together.')
        st.code('exam_records = COUNT(exam details in group)\ncaptured_exams = COUNT(IMAGE_CAPTURED_ON IS NOT NULL)\nuncaptured_exams = exam_records - captured_exams\nsuspected_uncaptured = uncaptured_exams if exam_records > 1\n    and captured_exams > 0 and matching_keys_complete else 0\nwhat_if_exams = exam_records - suspected_uncaptured\nDaily values = SUM(group values for that order_day)',language=None)
        st.info('Example: 3 matching registrations, 1 with capture → 2 suspected extras → what-if count 1. If all 3 have capture, retain all 3. If none has capture, retain all 3.')
    for path in ['sql/sqlserver/investigation_groups.sql','sql/postgres/06_investigation_groups.sql',
                 'sql/postgres/dashboard/investigation_summary.sql','sql/postgres/dashboard/investigation_daily.sql',
                 'sql/postgres/dashboard/investigation_candidates.sql']:
        with st.expander(path):st.code((ROOT/path).read_text(),language='sql')
    st.caption(f"Full-history group refresh: {audit.iloc[0]['loaded_at']}. Independent of the exam-star refresh, not a synchronized source snapshot. Patient and visit identifiers are not displayed or stored in this mart.")
