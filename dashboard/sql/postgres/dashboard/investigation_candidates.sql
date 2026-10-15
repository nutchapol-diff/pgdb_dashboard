SELECT f.order_day AS "Order date", COALESCE(m.modality_name,'Unknown modality') AS "Modality",
       COALESCE(e.exam_name,'Unknown exam') AS "Exam", f.exam_records AS "Recorded exams",
       f.captured_exams AS "With capture", f.suspected_uncaptured AS "Suspected extra registrations",
       f.exam_records-f.suspected_uncaptured AS "What-if exams"
FROM mart.investigation_groups f
LEFT JOIN dw.dim_modality m USING (modality_id)
LEFT JOIN dw.dim_exam e USING (exam_id)
WHERE {where} AND f.suspected_uncaptured>0
ORDER BY f.suspected_uncaptured DESC,f.order_day DESC,f.anchor_order_id,f.exam_id LIMIT 50;
