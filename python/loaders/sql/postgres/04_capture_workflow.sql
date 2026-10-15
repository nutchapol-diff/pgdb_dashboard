CREATE TABLE IF NOT EXISTS mart.capture_workflow (
    order_id integer NOT NULL,
    exam_id integer NOT NULL,
    log_entries bigint NOT NULL CHECK (log_entries > 0),
    paired_entries bigint NOT NULL CHECK (paired_entries BETWEEN 0 AND log_entries),
    first_started_at timestamptz,
    last_ended_at timestamptz,
    PRIMARY KEY (order_id, exam_id)
);
CREATE TABLE IF NOT EXISTS mart.capture_workflow_load_audit (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    source_database text NOT NULL,
    source_max_order_id integer,
    workflow_exams bigint NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
