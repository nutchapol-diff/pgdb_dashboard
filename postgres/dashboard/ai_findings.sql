-- Weighted means from score sum / score count; not averages of daily averages.
SELECT COALESCE(NULLIF(a.finding_name,''),'Unnamed') AS finding_name,
       sum(a.event_count)::bigint AS finding_records,
       sum(a.score_count)::bigint AS scored_records,
       sum(a.score_sum) / NULLIF(sum(a.score_count),0) AS mean_score,
       min(a.score_min) AS min_score, max(a.score_max) AS max_score
FROM mart.ai_finding_daily a
LEFT JOIN dw.dim_modality m ON m.modality_id = a.modality_id
WHERE {where}
GROUP BY a.finding_name ORDER BY mean_score DESC NULLS LAST LIMIT 25;
