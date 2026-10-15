-- Denominator includes ALL exam rows in the selected date/modality filter.
-- Group by name, matching the dashboard's modality selector.
WITH counts AS (
    SELECT m.modality_name, count(*)::bigint AS exam_records
    FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
    WHERE {where}
    GROUP BY m.modality_name
)
SELECT modality_name, exam_records,
       sum(exam_records) OVER ()::bigint AS selected_exam_records,
       100.0 * exam_records / NULLIF(sum(exam_records) OVER (),0) AS share_pct
FROM counts
ORDER BY exam_records DESC, modality_name;
