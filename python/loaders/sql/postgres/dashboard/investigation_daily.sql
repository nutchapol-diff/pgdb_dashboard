SELECT f.order_day, sum(f.exam_records)::bigint AS exam_records,
       sum(f.captured_exams)::bigint AS captured_exams,
       sum(f.suspected_uncaptured)::bigint AS suspected_uncaptured,
       sum(f.exam_records-f.suspected_uncaptured)::bigint AS what_if_exams
FROM mart.investigation_groups f LEFT JOIN dw.dim_modality m USING (modality_id)
WHERE {where} GROUP BY f.order_day ORDER BY f.order_day;
