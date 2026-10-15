SELECT 'exam'::text AS dataset, source_database,
       source_exam_count AS source_records, loaded_exam_count AS loaded_records,
       (to_jsonb(a)->>'unmapped_exam_count')::bigint AS excluded_records,
       NULL::bigint AS undated_records, finished_at,
       'Source count covers RIS_ORDERDTL joined to RIS_ORDER. NOLOCK extraction; count equality does not prove a consistent source snapshot.'::text AS consistency_note
FROM dw.load_audit a
WHERE status = 'complete'
ORDER BY load_id DESC LIMIT 1;
