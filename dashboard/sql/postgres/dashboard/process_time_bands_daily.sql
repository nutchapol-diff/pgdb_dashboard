-- Disjoint descriptive bands, not clinical SLA targets. Excludes invalid/missing totals.
SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
       count(*)::bigint AS valid_samples,
       count(*) FILTER (WHERE f.order_to_report_min <= 240)::bigint AS within_four_hours,
       count(*) FILTER (WHERE f.order_to_report_min > 240 AND f.order_to_report_min <= 1440)::bigint AS four_to_24_hours,
       count(*) FILTER (WHERE f.order_to_report_min > 1440 AND f.order_to_report_min <= 2880)::bigint AS hours_24_to_48,
       count(*) FILTER (WHERE f.order_to_report_min > 2880)::bigint AS over_48_hours
FROM mart.exam_timing f
WHERE {where} AND f.order_to_report_min IS NOT NULL
GROUP BY 1 ORDER BY 1;
