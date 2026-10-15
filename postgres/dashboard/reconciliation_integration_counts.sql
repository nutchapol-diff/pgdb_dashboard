-- Aggregate row count and represented source-record count are different grains.
-- Undated records are INCLUDED in represented_records, never added a second time.
SELECT 'ai_result_daily'::text AS dataset, count(*)::bigint AS stored_rows,
       COALESCE(sum(event_count),0)::bigint AS represented_records,
       0::bigint AS excluded_records,
       COALESCE(sum(event_count) FILTER (WHERE event_day IS NULL),0)::bigint AS undated_records
FROM mart.ai_result_daily
UNION ALL
SELECT 'ai_finding_daily', count(*)::bigint, COALESCE(sum(event_count),0)::bigint,
       0::bigint, COALESCE(sum(event_count) FILTER (WHERE event_day IS NULL),0)::bigint
FROM mart.ai_finding_daily
UNION ALL
SELECT 'hl7_ie_daily', count(*)::bigint, COALESCE(sum(event_count),0)::bigint,
       0::bigint, COALESCE(sum(event_count) FILTER (WHERE event_day IS NULL),0)::bigint
FROM mart.hl7_ie_daily
UNION ALL
SELECT 'hl7_transaction_daily', count(*)::bigint, COALESCE(sum(event_count),0)::bigint,
       0::bigint, COALESCE(sum(event_count) FILTER (WHERE event_day IS NULL),0)::bigint
FROM mart.hl7_transaction_daily;
