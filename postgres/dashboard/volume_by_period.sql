-- First bound parameter: day, week (Monday start), or month.
-- Count orders directly within each period; do not sum daily distinct counts.
SELECT date_trunc(%s, f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS period_start,
       count(DISTINCT f.order_id)::bigint AS orders,
       count(*)::bigint AS exams
FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
WHERE {where}
GROUP BY 1 ORDER BY 1;
