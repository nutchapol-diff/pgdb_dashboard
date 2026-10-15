-- Operational timestamps only; no source IDs, accessions or patient identifiers.
SELECT f.ordered_at, f.image_captured_at, f.first_finalized_at,
       f.finalized_at, f.is_deleted, f.technical_take_count,
       m.modality_name
FROM dw.fact_exam f
JOIN dw.dim_modality m USING (modality_id)
WHERE {where}
ORDER BY f.ordered_at DESC, f.order_id DESC, f.exam_id DESC
LIMIT 20;
