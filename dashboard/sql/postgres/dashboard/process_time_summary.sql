SELECT count(*)::bigint AS exams,
       count(f.order_to_capture_min)::bigint AS capture_samples,
       count(f.capture_to_report_min)::bigint AS report_after_capture_samples,
       count(f.order_to_report_min)::bigint AS total_samples,
       count(*) FILTER (WHERE f.image_captured_at IS NULL)::bigint AS missing_capture,
       count(*) FILTER (WHERE f.report_at IS NULL)::bigint AS missing_report,
       count(*) FILTER (WHERE f.capture_before_order)::bigint AS capture_before_order,
       count(*) FILTER (WHERE f.report_before_capture)::bigint AS report_before_capture,
       count(*) FILTER (WHERE f.report_before_order)::bigint AS report_before_order,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.order_to_capture_min) AS capture_p50,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY f.order_to_capture_min) AS capture_p90,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.capture_to_report_min) AS reading_p50,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY f.capture_to_report_min) AS reading_p90,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY f.order_to_report_min) AS total_p50,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY f.order_to_report_min) AS total_p90,
       count(*) FILTER (WHERE f.order_to_report_min > 240)::bigint AS over_four_hours,
       round(100.0 * count(*) FILTER (WHERE f.order_to_report_min > 240)
             / nullif(count(f.order_to_report_min), 0), 1) AS over_four_hours_pct
FROM mart.exam_timing f
WHERE {where};
