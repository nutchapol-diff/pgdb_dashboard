INSERT INTO dw.load_audit (source_database, source_exam_count,
    loaded_exam_count, source_max_order_at, source_max_result_at,
    unmapped_exam_count, status, finished_at)
VALUES (%s, %s, %s, %s, %s, %s, 'complete', clock_timestamp());
