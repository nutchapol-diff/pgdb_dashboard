-- Keep raw codes; no inferred priority meanings or SLA. Include missing-report coverage.
SELECT COALESCE(NULLIF(btrim(f.priority_code), ''), 'Unknown') AS priority_code,
       count(*)::bigint AS active_exams,
       count(f.order_to_report_min)::bigint AS valid_samples,
       count(*) FILTER (WHERE f.report_at IS NULL)::bigint AS missing_report,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.order_to_report_min) / 60 AS p50_hours,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY f.order_to_report_min) / 60 AS p90_hours
FROM mart.exam_timing f
WHERE {where}
GROUP BY 1 ORDER BY 1;
