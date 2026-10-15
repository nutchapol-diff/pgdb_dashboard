SELECT m.modality_name AS "Modality",
       count(*)::bigint AS "Exams",
       count(f.order_to_capture_min)::bigint AS "Capture n",
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.order_to_capture_min))::numeric, 1) AS "Capture p50 (min)",
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY f.order_to_capture_min))::numeric, 1) AS "Capture p90 (min)",
       count(f.capture_to_report_min)::bigint AS "Reading n",
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.capture_to_report_min))::numeric, 1) AS "Reading p50 (min)",
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY f.capture_to_report_min))::numeric, 1) AS "Reading p90 (min)",
       count(f.order_to_report_min)::bigint AS "Total n",
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.order_to_report_min))::numeric, 1) AS "Total p50 (min)",
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY f.order_to_report_min))::numeric, 1) AS "Total p90 (min)",
       round(100.0 * count(*) FILTER (WHERE f.order_to_report_min > 240)
             / nullif(count(f.order_to_report_min), 0), 1) AS ">4h pct"
FROM mart.exam_timing f
JOIN dw.dim_modality m USING (modality_id)
WHERE {where}
GROUP BY m.modality_id, m.modality_name
ORDER BY "Exams" DESC, m.modality_name;
