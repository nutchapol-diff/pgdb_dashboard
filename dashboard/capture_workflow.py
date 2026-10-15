"""Historical TECHWORKS workflow duration and inspectable source lineage."""
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
LABEL = 'Capture workflow duration (TECHWORKS)'


def render_capture_workflow(query, sql, where, params, source_database, explorer=False):
    st.subheader(LABEL)
    ready = query("SELECT to_regclass('mart.capture_workflow_load_audit') IS NOT NULL AS ready").iloc[0]['ready']
    audit = query('SELECT * FROM mart.capture_workflow_load_audit') if ready else pd.DataFrame()
    if audit.empty or audit.iloc[0]['source_database'] != source_database:
        st.info('Unavailable: capture workflow data is not loaded for this source.')
        return
    st.caption('Total recorded image-capture workflow time: earliest TECHWORKS start → latest end for each exam. Includes pauses between records. This does not measure patient waiting time or the percentage of time a scanner is busy.')
    rows = query(sql('capture_workflow_daily.sql', where), params)
    if rows.empty:
        st.info('No complete recorded capture workflows in this selection.')
    else:
        st.markdown('**Read this chart:** Green = median (middle duration). Orange = 90th percentile (90% of measured exams finished within this duration). Both lines use **minutes**, not hours or exam counts.')
        fig = go.Figure()
        for field,name,color in [('median_minutes','Median duration (min)','#207a78'),('p90_minutes','90th percentile duration (min)','#d3a247')]:
            fig.add_trace(go.Scatter(
                x=rows['order_day'], y=rows[field], name=name,
                mode='lines+markers+text', line={'color':color},
                text=[f'{value:,.1f} min' for value in rows[field]],
                textposition='bottom center' if field == 'median_minutes' else 'top center',
                textfont={'color':color,'size':12}, cliponaxis=False,
                customdata=rows[['completed_exams']].to_numpy(),
                hovertemplate='Order date: %{x|%d %b %Y}<br>'+name+': %{y:,.1f} min<br>Exams measured that day: %{customdata[0]:,}<extra></extra>',
            ))
        fig.update_layout(
            template='plotly_white', height=380,
            font={'family':'Arial','color':'#15233b','size':13},
            xaxis={'title':{'text':'Order date (Bangkok time)','font':{'color':'#15233b'}},'tickformat':'%d %b %Y','tickfont':{'color':'#516175'}},
            yaxis={'title':{'text':'Elapsed capture-workflow duration (minutes)','font':{'color':'#15233b'}},'ticksuffix':' min','tickfont':{'color':'#516175'},'rangemode':'tozero'},
            legend={'orientation':'h','y':1.15,'font':{'color':'#15233b'}},
            hoverlabel={'bgcolor':'white','font_color':'#15233b'},
            margin={'t':65,'b':65,'l':85,'r':35},
            paper_bgcolor='white', plot_bgcolor='white',
        )
        st.plotly_chart(fig,width='stretch',theme=None)
        st.markdown('**Calculation for each exam:** `workflow_minutes = seconds(last_ended_at − first_started_at) / 60`. These columns are the earliest `RIS_TECHWORKS.START_TIME` and latest `RIS_TECHWORKS.END_TIME` for that exam. **Example:** 09:00 → 09:25 = **25 min**, including any pauses.')
        st.caption('Group exam durations by Bangkok order date, then calculate the median and 90th percentile for each day. Only active exam details with every recorded workflow entry complete and in the correct time order are measured. This is elapsed workflow time, not patient waiting time or scanner busy time.')
        with st.expander('Daily chart values and number of exams measured'):
            st.dataframe(rows.rename(columns={'order_day':'Order date (Bangkok)','completed_exams':'Exams measured','median_minutes':'Median duration (min)','p90_minutes':'90th percentile duration (min)'}),hide_index=True,width='stretch')
        st.caption('The latest source day may be partial. Compare days with similar coverage; a low duration alone does not prove improved service.')
    if explorer:
        st.markdown('**Before → transform → after**')
        st.write('RIS_TECHWORKS.ACCESSION_NO joins RIS_ORDERDTL.ACCESSION_NO. Group by ORDER_ID + EXAM_ID; retain log count, number of entries with both times in the correct order, earliest START_TIME and latest END_TIME. Store only exam keys and workflow summaries in mart.capture_workflow; accession and clinical text are not copied.')
        st.code('workflow_minutes = (latest END_TIME − earliest START_TIME) / 60 seconds\nInclude only exams where every log entry has START_TIME and END_TIME ≥ START_TIME.\nDaily median / p90 = percentile_cont(0.5 / 0.9) of eligible exam durations.',language=None)
        st.caption('For repeated or overlapping entries, measure from the first start to the last end, including any gaps. Do not add the entry durations together. START_TIME is labelled workflow start; separate call/preparation/scan phases cannot be inferred from these two columns. Exams use active detail status and the current order-date/modality-type filters.')
        st.dataframe(rows,hide_index=True,width='stretch')
        st.markdown('**Saved exam records and calculated workflow time: up to 20 exams**')
        st.dataframe(query(sql('capture_workflow_sample.sql',where),params),hide_index=True,width='stretch')
        st.caption(f"Source: {audit.iloc[0]['source_database']}; loaded {audit.iloc[0]['loaded_at']}; {audit.iloc[0]['workflow_exams']:,} source exam summaries. Separate refresh, not a synchronized source snapshot.")
        for path in ['sql/sqlserver/techworks_workflow_page.sql','sql/postgres/04_capture_workflow.sql','sql/postgres/load/aggregate_capture_workflow.sql','sql/postgres/load/replace_capture_workflow.sql','sql/postgres/dashboard/capture_workflow_daily.sql','sql/postgres/dashboard/capture_workflow_sample.sql']:
            with st.expander(path):
                st.code((ROOT/path).read_text(encoding='utf-8'),language='sql')
