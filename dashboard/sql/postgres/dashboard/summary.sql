SELECT count(DISTINCT f.order_id)::bigint AS orders,
       count(*)::bigint AS exams,
       count(*) FILTER (WHERE f.image_captured_at IS NOT NULL)::bigint AS captured_exams,
       count(*) FILTER (WHERE COALESCE(f.first_finalized_at, f.finalized_at) IS NOT NULL)::bigint AS finalized_exams,
       count(*) FILTER (WHERE f.technical_take_count > 1)::bigint AS multiple_takes
FROM dw.fact_exam f
WHERE {where};
