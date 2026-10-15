SELECT m.modality_name, count(*)::bigint AS exam_count
FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
WHERE {where} AND f.image_captured_at IS NOT NULL
  AND f.first_finalized_at IS NULL AND f.finalized_at IS NULL
GROUP BY 1 ORDER BY exam_count DESC LIMIT 10;
