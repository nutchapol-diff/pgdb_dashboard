-- One exam's envelope, not summed log durations or scanner utilization.
WITH intervals AS (
 SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_day,
        EXTRACT(EPOCH FROM (w.last_ended_at-w.first_started_at))/60.0 AS minutes
 FROM dw.fact_exam f
 JOIN dw.dim_modality m USING (modality_id)
 JOIN mart.capture_workflow w USING (order_id,exam_id)
 WHERE {where} AND f.is_deleted IS FALSE
   AND w.log_entries=w.paired_entries
   AND w.first_started_at IS NOT NULL AND w.last_ended_at>=w.first_started_at
)
SELECT order_day,COUNT(*) AS completed_exams,
       percentile_cont(.5) WITHIN GROUP (ORDER BY minutes) AS median_minutes,
       percentile_cont(.9) WITHIN GROUP (ORDER BY minutes) AS p90_minutes
FROM intervals GROUP BY order_day ORDER BY order_day;
