-- A single statement observes the fact and quarantine in one PostgreSQL snapshot.
SELECT 'exam'::text AS dataset,
       count(*)::bigint AS stored_rows, count(*)::bigint AS represented_records,
       (SELECT count(*)::bigint FROM dw.fact_exam_unmapped) AS excluded_records,
       NULL::bigint AS undated_records
FROM dw.fact_exam;
