INSERT INTO capture_stage
SELECT order_id,exam_id,count(*),
       count(*) FILTER (WHERE started_at IS NOT NULL AND ended_at>=started_at),
       min(started_at),max(ended_at)
FROM capture_logs GROUP BY order_id,exam_id;
