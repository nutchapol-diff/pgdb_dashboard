"""Column equations and table paths for the offline widget diagram.

Documentation metadata only. SQL remains the executable definition.
"""

TAT = "report_at = COALESCE(first_finalized_at, finalized_at)\ntat_min = seconds(report_at − ordered_at) / 60\nDuration statistics include only report_at ≥ ordered_at"
IQR = "q1_min = percentile(tat_min, 25%) per order_date\nq3_min = percentile(tat_min, 75%) per order_date\niqr_min = q3_min − q1_min\nlower_cutoff_min = q1_min − 1.5 × iqr_min\nupper_cutoff_min = q3_min + 1.5 × iqr_min"


def equations(filename):
    """Use actual query column names, including temporary SELECT aliases."""
    formulas = {
        'investigation_summary.sql': "Use detail SERVICE_TYPE = 1; if NULL, use exam-definition SERVICE_TYPE = '1'\nExclude IS_DELETED = Y and IS_CANCELED = Y\nGroup by organization + patient + day + exam + modality, optionally visit\nexam_records = COUNT(exam details in group)\ncaptured_exams = COUNT(IMAGE_CAPTURED_ON not NULL)\nsuspected_uncaptured = exam_records − captured_exams when exam_records > 1, captured_exams > 0 and matching_keys_complete\nOtherwise suspected_uncaptured = 0\nwhat_if_exams = exam_records − suspected_uncaptured\nSelected totals = SUM(group counts) for ONE match_rule\nSuspected, not confirmed duplicates; raw orders retained",
        'capture_workflow_daily.sql': 'minutes = seconds(last_ended_at − first_started_at) / 60\nInclude only log_entries = paired_entries and last_ended_at ≥ first_started_at\ncompleted_exams = COUNT(exam rows)\nmedian_minutes = percentile(minutes, 50%)\np90_minutes = percentile(minutes, 90%)\nGroup by order_day = Bangkok date(ordered_at)',
        'stroke_summary.sql': TAT + '\ncapture_over30 = COUNT(image_captured_at > ordered_at + 30 min)\nfinal_over30 = COUNT(report_at > ordered_at + 30 min)\nOnly candidate order_id, priority_code = S, is_deleted = false, is_canceled = false',
        'daily.sql': TAT + '\norders = COUNT(DISTINCT order_id)\nexams = COUNT(exam rows, including untimed exams)\nmedian_tat_min = percentile(tat_min, 50%)\noutliers = COUNT(tat_min > 240)\nGroup by order_date = Bangkok date(ordered_at)',
        'tat_box_daily.sql': TAT + '\n' + IQR + '\nmean_min = SUM(tat_min) / COUNT(tat_min)\niqr_outliers = COUNT(tat_min < lower_cutoff_min OR tat_min > upper_cutoff_min)\nover_four_hours = COUNT(tat_min > 240)\nlow_outlier_mean_min = AVG(tat_min where tat_min < lower_cutoff_min)\nhigh_outlier_mean_min = AVG(tat_min where tat_min > upper_cutoff_min)\nnormal_mean_min = AVG(tat_min where lower_cutoff_min ≤ tat_min ≤ upper_cutoff_min)\nWhiskers = MIN / MAX(tat_min within fences)\nAll statistics grouped by order_date',
        'volume_by_period.sql': 'period_start = date_trunc(selected day/week/month, Bangkok ordered_at)\norders = COUNT(DISTINCT order_id)\nexams = COUNT(exam rows)\nGroup by period_start; empty displayed periods filled with 0',
        'modality_share.sql': 'exam_records = COUNT(exam rows) per modality_name\nselected_exam_records = SUM(exam_records across selected modalities)\nshare_pct = 100 × exam_records / selected_exam_records',
        'summary.sql': 'orders = COUNT(DISTINCT order_id)\nexams = COUNT(exam rows)\ncaptured_exams = COUNT(image_captured_at IS NOT NULL)\nfinalized_exams = COUNT(COALESCE(first_finalized_at, finalized_at) IS NOT NULL)\nmultiple_takes = COUNT(technical_take_count > 1)\nmultiple_takes is a legacy SQL name for multiple workflow entries',
        'top_exams.sql': '"Exam records" = COUNT(exam rows) per exam_name\nSort descending; show largest 10',
        'orders_by_modality_top10.sql': 'order_count = COUNT(DISTINCT order_id) per modality_name\nSort descending; show largest 10',
        'top_producers.sql': '"Reports" = SUM(finalized_reports) per display_name\nFilter by report_date; sort descending; show largest 10\nNo modality filter',
        'process_time_stages_daily.sql': 'Use rows with both order_to_capture_min and capture_to_report_min\norder_capture_mean_hours = AVG(order_to_capture_min) / 60\ncapture_report_mean_hours = AVG(capture_to_report_min) / 60\ntotal_mean_hours = AVG(order_to_report_min) / 60\ntotal_mean_hours = order_capture_mean_hours + capture_report_mean_hours\nGroup by Bangkok date(ordered_at)',
        'process_time_bands_daily.sql': 'valid_samples = COUNT(order_to_report_min IS NOT NULL)\nwithin_four_hours = COUNT(order_to_report_min ≤ 240)\nfour_to_24_hours = COUNT(240 < order_to_report_min ≤ 1440)\nhours_24_to_48 = COUNT(1440 < order_to_report_min ≤ 2880)\nover_48_hours = COUNT(order_to_report_min > 2880)\nDisplayed band share = 100 × band count / valid_samples\nGroup by Bangkok date(ordered_at)',
        'process_time_priority.sql': 'priority_code = trimmed priority_code, blank/missing → Unknown\np50_hours = percentile(order_to_report_min, 50%) / 60\np90_hours = percentile(order_to_report_min, 90%) / 60\nactive_exams = COUNT(exam rows)\nvalid_samples = COUNT(order_to_report_min)\nmissing_report = COUNT(report_at IS NULL)\nGroup by priority_code',
        'process_time_daily.sql': 'p50_min = percentile(order_to_report_min, 50%)\np90_min = percentile(order_to_report_min, 90%)\nvalid_samples = COUNT(order_to_report_min)\nover_four_hours = COUNT(order_to_report_min > 240)\nGroup by Bangkok date(ordered_at)',
        'process_time_summary.sql': 'capture_p50 / capture_p90 = percentile(order_to_capture_min, 50% / 90%)\nreading_p50 / reading_p90 = percentile(capture_to_report_min, 50% / 90%)\ntotal_p50 / total_p90 = percentile(order_to_report_min, 50% / 90%)\nover_four_hours = COUNT(order_to_report_min > 240)\ntotal_samples = COUNT(order_to_report_min)\nover_four_hours_pct = 100 × over_four_hours / total_samples\nEach phase uses its own non-NULL durations',
        'process_time_by_modality.sql': 'Capture p50 / p90 = percentile(order_to_capture_min, 50% / 90%)\nReading p50 / p90 = percentile(capture_to_report_min, 50% / 90%)\nTotal p50 / p90 = percentile(order_to_report_min, 50% / 90%)\n>4h pct = 100 × COUNT(order_to_report_min > 240) / COUNT(order_to_report_min)\nGroup by modality_id and modality_name',
        'ai_activity.sql': 'result_records = SUM(event_count)\nscored_records = SUM(score_count)\nmean_score = SUM(score_sum) / SUM(score_count)\nreviewed_records = SUM(reviewed_count)\nagreed_records = SUM(agreed_count)\ndisagreed_records = SUM(disagreed_count)\nGroup by event_day; card totals selected daily result_records',
        'ai_scores.sql': 'result_records = SUM(event_count) per score_bucket\nBuckets: [0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]\nMissing and Outside 0–1 are separate buckets',
        'ai_findings.sql': 'finding_records = SUM(event_count)\nscored_records = SUM(score_count)\nmean_score = SUM(score_sum) / SUM(score_count)\nmin_score = MIN(score_min); max_score = MAX(score_max)\nGroup by finding_name; show largest 25 mean_score values',
        'hl7_activity.sql': 'log_records = SUM(event_count)\nGroup by event_day and ack_code\nExclude is_deleted = Y; blank ack_code → No ACK code',
        'hl7_outcomes.sql': 'log_records = SUM(event_count)\nGroup by status_code and ack_code\nExclude is_deleted = Y; codes remain uninterpreted',
        'hl7_routes.sql': 'log_records = SUM(event_count)\nwith_ack_code = SUM(event_count where trimmed ack_code is not blank)\nGroup by sender, receiver, message_type\nExclude is_deleted = Y; show largest 20 log_records groups',
        'hl7_delays.sql': 'transaction_records = SUM(event_count)\nvalid_delay_records = SUM(valid_delay_count)\nmean_delay_seconds = SUM(delay_ms_sum) / SUM(valid_delay_count) / 1000\ndelay_le_1s = SUM(saved delay_le_1s)\ndelay_1_5s = SUM(saved delay_1_5s)\ndelay_5_30s = SUM(saved delay_5_30s)\ndelay_gt_30s = SUM(saved delay_gt_30s)\nGroup by event_day\nMissing timestamps → unavailable delay, not 0 seconds',
        'integration_audit.sql': 'source_rows = number of source records at extraction\nloaded_rows = SUM(event_count) in the corresponding saved mart\nCheck source_rows = loaded_rows\nundated_rows = SUM(event_count where event_day IS NULL)\nfinished_at = completed refresh time; group by dataset',
        'reconciliation_exam_audit.sql': 'source_records = source_exam_count from latest complete dw.load_audit\nloaded_records = loaded_exam_count\nstored_rows = COUNT(dw.fact_exam rows)\nexcluded_records = COUNT(dw.fact_exam_unmapped rows)\nCheck source_records = stored_rows + excluded_records\nCounts query uses one PostgreSQL snapshot; source was not a consistent snapshot',
    }
    return formulas[filename]


def lineage(filename, sources):
    """Nodes explicitly distinguish stored relations from calculated query values."""
    nodes = [dict(id=f's{i}', title=s[0], body=s[1], stage=0, level=0) for i, s in enumerate(sources)]
    edges = []

    def relation(key, title, body, level=1, parents=None):
        nodes.append(dict(id=key, title=title, body=body, stage=2, level=level))
        edges.extend([parent, key] for parent in (parents if parents is not None else [n['id'] for n in nodes if n['level'] == 0]))
        return key

    timing = filename.startswith('process_time')
    if filename.startswith('ai_') and filename != 'integration_audit.sql':
        finding = filename == 'ai_findings.sql'
        score = 'FINDING_SCORE' if finding else 'ABNORMALITY_SCORE'
        body = f'SAVED TABLE · daily grouped records\nevent_day = date(RIS_EXAMRESULTAI.CREATED_ON)\nevent_count = COUNT(source rows)\nscore_count = COUNT(non-NULL {score})\nscore_sum = SUM({score}); missing sum → 0\nmodality_id ← RIS_ORDERDTL.MODALITY_ID'
        body += '\nfinding_name ← FINDING_NAME\nscore_min / score_max = MIN / MAX(FINDING_SCORE)' if finding else '\nscore_bucket = band(ABNORMALITY_SCORE)\nreviewed_count = COUNT(RAD_AGREED in Y,N)\nagreed_count = COUNT(RAD_AGREED = Y)\ndisagreed_count = COUNT(RAD_AGREED = N)'
        output = relation('ai', 'mart.ai_finding_daily' if finding else 'mart.ai_result_daily', body)
        relation('modality', 'dw.dim_modality', 'SAVED TABLE\nmodality_id ← MODALITY_ID\nmodality_type ← MODALITY_TYPE\nmodality_type_name ← TYPE_NAME', parents=['s1'])
        nodes[-2]['body'] += '\nGroup by event_day, modality_id, ' + ('finding_name' if finding else 'score_bucket')
        outputs = [output, 'modality']
    elif filename.startswith('hl7_'):
        delay = filename == 'hl7_delays.sql'
        body = 'SAVED TABLE · daily grouped logs\nevent_day = date(TRANS_TIMESTAMP)\ndelay_ms = milliseconds(ACK_TIMESTAMP − TRANS_TIMESTAMP)\nOnly ACK_TIMESTAMP ≥ TRANS_TIMESTAMP\nvalid_delay_count = COUNT(delay_ms)\ndelay_ms_sum = SUM(delay_ms)\nevent_count = COUNT(source rows)\nBand counts from delay_ms' if delay else 'SAVED TABLE · daily grouped logs\nevent_day = date(CREATED_ON)\nsender / receiver ← SENDER / RECEIVER\nmessage_type ← MESSAGE_TYPE\nstatus_code ← STATUS\nack_code ← ACKNOWLEDGMENT_CODE\nis_deleted ← IS_DELETED\nevent_count = COUNT(source rows)'
        body += '\nGroup by event_day, message_type, trans_type, trans_with' if delay else '\nGroup by event_day, sender, receiver, message_type, status_code, ack_code, is_deleted'
        outputs = [relation('hl7', 'mart.hl7_transaction_daily' if delay else 'mart.hl7_ie_daily', body)]
    elif filename == 'investigation_summary.sql':
        outputs = [relation('investigations','mart.investigation_groups','SAVED GROUP TABLE\nmatch_rule = same_visit or same_day\norder_day = Bangkok date(ORDER_START_TIME)\nanchor_order_id = MIN(ORDER_ID) within group\nexam_id, modality_id ← RIS_ORDERDTL\nexam_records = COUNT(group members)\ncaptured_exams = COUNT(IMAGE_CAPTURED_ON not NULL)\nsuspected_uncaptured = unmatched capture registrations in repeated captured groups\nPatient and visit fields used at source only; not stored')]
        outputs.append(relation('modality','dw.dim_modality','SAVED DIMENSION\nmodality_id, modality_type and names\nFilters the groups by modality type',parents=[n['id'] for n in nodes if n['title'].startswith('RIS_MODALITY')]))
    elif filename == 'integration_audit.sql':
        outputs = [relation('audit', 'mart.integration_load_audit', 'SAVED TABLE\ndataset, source_rows, loaded_rows\nundated_rows, finished_at\nCounts captured by load_ai_hl7.py')]
    elif filename == 'reconciliation_exam_audit.sql':
        outputs = [relation('audit', 'dw.load_audit', 'SAVED TABLE · completed extract counts\nsource_exam_count, loaded_exam_count\nunmapped_exam_count, finished_at'), relation('fact', 'dw.fact_exam + dw.fact_exam_unmapped', 'SAVED TABLES\nMapped exam rows + separately retained rows\nActual row counts checked against audit')]
    else:
        fact_sources = [n['id'] for n in nodes if n['level'] == 0 and not n['title'].startswith('RIS_MODALITY') and not n['title'].startswith('RIS_EXAM →') and n['title'] != 'RIS_EXAM']
        body = 'SAVED TIMESCALE TABLE · one exam detail\norder_id / exam_id ← RIS_ORDERDTL keys\nordered_at ← RIS_ORDER.ORDER_START_TIME\nmodality_id ← RIS_ORDERDTL.MODALITY_ID\nTimes interpreted as Bangkok time'
        if any(s[0] == 'RIS_EXAMRESULT' for s in sources):
            body += '\nfirst_finalized_at ← RIS_EXAMRESULT.FIRSTFINALIZED_ON\nfinalized_at ← RIS_EXAMRESULT.FINALIZED_ON'
        if any('IMAGE_CAPTURED_ON' in s[1] for s in sources):
            body += '\nimage_captured_at ← RIS_ORDERDTL.IMAGE_CAPTURED_ON'
        if timing or filename == 'stroke_summary.sql':
            body += '\npriority_code ← RIS_ORDERDTL.PRIORITY\nis_deleted: Y → true; N → false'
        if filename == 'summary.sql':
            body += '\ntechnical_take_count = COUNT(RIS_TECHWORKS rows per accession)'
        if filename == 'top_producers.sql':
            body += '\nradiologist_id ← FINALIZED_BY matched to HR_EMP.EMP_ID (IS_RADIOLOGIST = Y)'
        if filename == 'capture_workflow_daily.sql':
            fact_sources = ['s0', 's1']
            body = 'SAVED TIMESCALE TABLE · one exam detail\norder_id / exam_id ← RIS_ORDERDTL keys\nordered_at ← RIS_ORDER.ORDER_START_TIME\nmodality_id ← RIS_ORDERDTL.MODALITY_ID\nis_deleted: Y → true; N → false'
        relation('fact', 'dw.fact_exam', body, parents=fact_sources)
        outputs = ['fact']
        modality_sources = [n['id'] for n in nodes if n['level'] == 0 and n['title'].startswith('RIS_MODALITY')]
        if modality_sources:
            outputs.append(relation('modality', 'dw.dim_modality', 'SAVED TABLE\nmodality_id ← MODALITY_ID\nmodality_name ← MODALITY_NAME\nmodality_type ← MODALITY_TYPE\nmodality_type_name ← TYPE_NAME\nJoin fact by modality_id', parents=modality_sources))
        if timing:
            outputs = [relation('timing', 'mart.exam_timing', 'VIEW · calculated when queried\nreport_at = COALESCE(first_finalized_at, finalized_at)\norder_to_capture_min = seconds(image_captured_at − ordered_at) / 60\ncapture_to_report_min = seconds(report_at − image_captured_at) / 60\norder_to_report_min = seconds(report_at − ordered_at) / 60\nEach missing/negative interval → NULL\nOnly is_deleted = false', level=2, parents=['fact'])] + outputs[1:]
        if filename == 'capture_workflow_daily.sql':
            outputs.append(relation('capture', 'mart.capture_workflow', 'SAVED TABLE · one summary per order_id + exam_id\nMatch ACCESSION_NO at source\nfirst_started_at = MIN(START_TIME)\nlast_ended_at = MAX(END_TIME)\nlog_entries = COUNT(TECHWORKS rows)\npaired_entries = COUNT(START_TIME not NULL and END_TIME ≥ START_TIME)\nJoin fact by order_id + exam_id', parents=['s1', 's3']))
        if filename == 'stroke_summary.sql':
            outputs.append(relation('stroke', 'mart.stroke_candidate_orders', 'SAVED TABLE\norder_id ← RIS_ORDER.ORDER_ID\nis_canceled ← RIS_ORDER.IS_CANCELED\nOnly CLINICAL_INSTRUCTION contains stroke\nJoin fact by order_id', parents=[n['id'] for n in nodes if n['level'] == 0 and n['title'] == 'RIS_ORDER']))
        if filename == 'top_exams.sql':
            outputs.append(relation('exam', 'dw.dim_exam', 'SAVED TABLE\nexam_id ← EXAM_ID\nexam_name ← EXAM_NAME\nJoin fact by exam_id', parents=[n['id'] for n in nodes if n['level'] == 0 and n['title'] == 'RIS_EXAM']))
        if filename == 'top_producers.sql':
            relation('radiologist', 'dw.dim_radiologist', 'SAVED TABLE\nemployee_id ← HR_EMP.EMP_ID\ndisplay_name ← HR_EMP name columns', parents=['s3'])
            relation('producer', 'mart.producer_daily', 'SAVED MATERIALIZED VIEW\nreport_date = Bangkok date(COALESCE(first_finalized_at, finalized_at))\nfinalized_reports = COUNT(finalized exam rows)\nGroup by report_date + radiologist_id', level=2, parents=['fact'])
            outputs = [relation('producer_view', 'mart.top_producers_daily', 'VIEW\nreport_date, finalized_reports ← mart.producer_daily\ndisplay_name ← dw.dim_radiologist\nJoin radiologist_id = employee_id', level=3, parents=['producer', 'radiologist'])]
    if filename in ('summary.sql','volume_by_period.sql','modality_share.sql','top_exams.sql'):
        outputs.append(relation('canceled', 'mart.canceled_orders', 'SAVED TABLE · explicit canceled order IDs\norder_id ← RIS_ORDER.ORDER_ID where IS_CANCELED = Y\nExclude matching fact_exam.order_id\nAlso exclude fact_exam.is_deleted = true\nRaw fact rows remain stored', parents=[n['id'] for n in nodes if n['stage'] == 0 and n['title'] == 'RIS_ORDER']))
    edges.extend([key, 'widget'] for key in outputs)
    nodes.append(dict(id='widget', title='Dashboard widget', body=equations(filename), stage=3, level=max(n['level'] for n in nodes)+1))
    return dict(nodes=nodes, edges=edges)
