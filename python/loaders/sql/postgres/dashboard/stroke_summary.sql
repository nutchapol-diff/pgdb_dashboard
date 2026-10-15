-- Historical completed intervals, not a current pending queue or confirmed stroke cohort.
SELECT count(*)::bigint AS eligible_exams,
       count(DISTINCT f.order_id)::bigint AS eligible_orders,
       count(*) FILTER (WHERE f.image_captured_at >= f.ordered_at)::bigint AS capture_valid,
       count(*) FILTER (WHERE f.image_captured_at > f.ordered_at + interval '30 minutes')::bigint AS capture_over30,
       count(*) FILTER (WHERE f.image_captured_at IS NULL)::bigint AS capture_missing,
       count(*) FILTER (WHERE f.image_captured_at < f.ordered_at)::bigint AS capture_invalid,
       count(*) FILTER (WHERE COALESCE(f.first_finalized_at,f.finalized_at) >= f.ordered_at)::bigint AS final_valid,
       count(*) FILTER (WHERE COALESCE(f.first_finalized_at,f.finalized_at) > f.ordered_at + interval '30 minutes')::bigint AS final_over30,
       count(*) FILTER (WHERE COALESCE(f.first_finalized_at,f.finalized_at) IS NULL)::bigint AS final_missing,
       count(*) FILTER (WHERE COALESCE(f.first_finalized_at,f.finalized_at) < f.ordered_at)::bigint AS final_invalid
FROM dw.fact_exam f
JOIN dw.dim_modality m USING (modality_id)
JOIN mart.stroke_candidate_orders s ON s.order_id = f.order_id
WHERE {where} AND f.priority_code = 'S'
  AND f.is_deleted IS FALSE AND s.is_canceled IS FALSE;
