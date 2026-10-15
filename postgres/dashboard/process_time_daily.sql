SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
       count(*)::bigint AS exams,
       count(f.order_to_report_min)::bigint AS valid_samples,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.order_to_report_min) AS p50_min,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY f.order_to_report_min) AS p90_min,
       count(*) FILTER (WHERE f.order_to_report_min > 240)::bigint AS over_four_hours
FROM mart.exam_timing f
WHERE {where}
GROUP BY 1 ORDER BY 1;
