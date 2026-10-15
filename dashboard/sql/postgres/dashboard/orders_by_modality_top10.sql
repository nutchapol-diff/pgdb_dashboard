SELECT m.modality_name, count(DISTINCT f.order_id)::bigint AS order_count
FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
WHERE {where} GROUP BY 1 ORDER BY order_count DESC LIMIT 10;
