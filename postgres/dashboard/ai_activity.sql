-- Dates refer to AI result CREATED_ON, not order date. Counts are result records.
SELECT a.event_day, sum(a.event_count)::bigint AS result_records,
       sum(a.score_count)::bigint AS scored_records,
       sum(a.score_sum) / NULLIF(sum(a.score_count),0) AS mean_score,
       sum(a.reviewed_count)::bigint AS reviewed_records,
       sum(a.agreed_count)::bigint AS agreed_records,
       sum(a.disagreed_count)::bigint AS disagreed_records
FROM mart.ai_result_daily a
LEFT JOIN dw.dim_modality m ON m.modality_id = a.modality_id
WHERE {where}
GROUP BY a.event_day ORDER BY a.event_day;
