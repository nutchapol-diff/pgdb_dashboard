INSERT INTO dw.dim_exam (exam_id, exam_name) VALUES %s
ON CONFLICT (exam_id) DO UPDATE SET exam_name=EXCLUDED.exam_name;
