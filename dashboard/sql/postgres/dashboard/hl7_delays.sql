SELECT event_day, sum(event_count)::bigint AS transaction_records,
       sum(sent_count)::bigint AS sent_records, sum(ack_count)::bigint AS ack_records,
       sum(valid_delay_count)::bigint AS valid_delay_records,
       sum(negative_delay_count)::bigint AS negative_delay_records,
       sum(delay_ms_sum) / NULLIF(sum(valid_delay_count),0) / 1000 AS mean_delay_seconds,
       sum(delay_le_1s)::bigint AS delay_le_1s, sum(delay_1_5s)::bigint AS delay_1_5s,
       sum(delay_5_30s)::bigint AS delay_5_30s, sum(delay_gt_30s)::bigint AS delay_gt_30s
FROM mart.hl7_transaction_daily
WHERE event_day BETWEEN %s AND %s
GROUP BY event_day ORDER BY event_day;
