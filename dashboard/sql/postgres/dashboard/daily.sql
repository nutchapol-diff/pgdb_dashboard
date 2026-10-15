SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
       count(DISTINCT f.order_id)::bigint AS orders,
       count(*)::bigint AS exams,
       count(*) FILTER (WHERE COALESCE(f.first_finalized_at,f.finalized_at) >
                             f.ordered_at + interval '4 hours')::bigint AS outliers,
       percentile_cont(0.5) WITHIN GROUP (
         ORDER BY EXTRACT(EPOCH FROM
           (COALESCE(f.first_finalized_at,f.finalized_at)-f.ordered_at))/60
       ) FILTER (WHERE COALESCE(f.first_finalized_at,f.finalized_at) >= f.ordered_at)
         AS median_tat_min
FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
WHERE {where} GROUP BY 1 ORDER BY 1;
