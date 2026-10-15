SELECT f.*, a.source_database, a.unmapped_exam_count
FROM mart.source_freshness f
CROSS JOIN (
    SELECT source_database,
           COALESCE((to_jsonb(a)->>'unmapped_exam_count')::bigint, 0) AS unmapped_exam_count
    FROM dw.load_audit a
    WHERE status = 'complete' ORDER BY load_id DESC LIMIT 1
) a;
