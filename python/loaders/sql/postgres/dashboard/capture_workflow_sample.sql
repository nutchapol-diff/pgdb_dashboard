SELECT f.order_id,f.exam_id,m.modality_name,w.log_entries,w.paired_entries,
       w.first_started_at,w.last_ended_at,
       CASE WHEN w.log_entries=w.paired_entries AND w.last_ended_at>=w.first_started_at
            THEN EXTRACT(EPOCH FROM (w.last_ended_at-w.first_started_at))/60.0 END AS workflow_minutes
FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
JOIN mart.capture_workflow w USING (order_id,exam_id)
WHERE {where} AND f.is_deleted IS FALSE
ORDER BY f.ordered_at DESC,f.order_id,f.exam_id LIMIT 20;
