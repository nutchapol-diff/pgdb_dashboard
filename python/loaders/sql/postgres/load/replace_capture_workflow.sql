DELETE FROM mart.capture_workflow;
INSERT INTO mart.capture_workflow SELECT * FROM capture_stage;
INSERT INTO mart.capture_workflow_load_audit
    (source_database,source_max_order_id,workflow_exams)
VALUES (%s,%s,%s)
ON CONFLICT (singleton) DO UPDATE SET
    source_database=EXCLUDED.source_database,
    source_max_order_id=EXCLUDED.source_max_order_id,
    workflow_exams=EXCLUDED.workflow_exams, loaded_at=now();
ANALYZE mart.capture_workflow;
