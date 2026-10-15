SELECT e.exam_name AS "Exam", count(*)::bigint AS "Exam records"
FROM dw.fact_exam f
JOIN dw.dim_exam e USING (exam_id)
JOIN dw.dim_modality m USING (modality_id)
WHERE {where}
GROUP BY e.exam_name
ORDER BY "Exam records" DESC, e.exam_name
LIMIT 10;
