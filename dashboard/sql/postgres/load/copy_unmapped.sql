-- PostgreSQL text COPY. Python escapes backslash, tab, newline, and carriage return;
-- unquoted \N represents SQL NULL. The column order matches the SQL Server extract.
COPY dw.fact_exam_unmapped (
    ordered_at, order_id, exam_id, modality_id, radiologist_id,
    priority_code, exam_status_code, result_status_code, exam_at,
    arrival_at, image_captured_at, qa_at, first_finalized_at,
    finalized_at, released_at, technical_take_count, source_modified_at,
    is_deleted
) FROM STDIN WITH (FORMAT text, DELIMITER E'\t', NULL '\N');
