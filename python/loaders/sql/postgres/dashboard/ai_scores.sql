SELECT a.score_bucket, sum(a.event_count)::bigint AS result_records
FROM mart.ai_result_daily a
LEFT JOIN dw.dim_modality m ON m.modality_id = a.modality_id
WHERE {where}
GROUP BY a.score_bucket ORDER BY a.score_bucket;
