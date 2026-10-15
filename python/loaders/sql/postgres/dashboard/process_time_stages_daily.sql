-- Same complete, chronologically valid cohort for both stages; means are additive.
SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
       count(*)::bigint AS complete_samples,
       avg(f.order_to_capture_min) / 60 AS order_capture_mean_hours,
       avg(f.capture_to_report_min) / 60 AS capture_report_mean_hours,
       avg(f.order_to_report_min) / 60 AS total_mean_hours
FROM mart.exam_timing f
WHERE {where}
  AND f.order_to_capture_min IS NOT NULL
  AND f.capture_to_report_min IS NOT NULL
GROUP BY 1 ORDER BY 1;
