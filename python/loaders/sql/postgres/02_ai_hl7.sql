-- Daily serving aggregates, not patient-level facts. Source dates are Bangkok dates.
-- Nullable dates preserve undated source records for coverage reporting.
CREATE TABLE IF NOT EXISTS mart.ai_result_daily (
    event_day date, modality_id integer, score_bucket text NOT NULL,
    event_count bigint NOT NULL, score_count bigint NOT NULL,
    score_sum numeric NOT NULL, reviewed_count bigint NOT NULL,
    agreed_count bigint NOT NULL, disagreed_count bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS ai_result_daily_date_modality
    ON mart.ai_result_daily (event_day, modality_id);
CREATE TABLE IF NOT EXISTS mart.ai_finding_daily (
    event_day date, modality_id integer, finding_name text,
    event_count bigint NOT NULL, score_count bigint NOT NULL,
    score_sum numeric NOT NULL, score_min double precision, score_max double precision
);
CREATE INDEX IF NOT EXISTS ai_finding_daily_date_modality
    ON mart.ai_finding_daily (event_day, modality_id);
CREATE TABLE IF NOT EXISTS mart.hl7_ie_daily (
    event_day date, sender text, receiver text, message_type text,
    status_code text, ack_code text, is_deleted text,
    event_count bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS hl7_ie_daily_date ON mart.hl7_ie_daily (event_day);
CREATE TABLE IF NOT EXISTS mart.hl7_transaction_daily (
    event_day date, message_type text, trans_type text, trans_with text,
    event_count bigint NOT NULL, sent_count bigint NOT NULL,
    ack_count bigint NOT NULL, valid_delay_count bigint NOT NULL,
    negative_delay_count bigint NOT NULL, delay_ms_sum numeric NOT NULL,
    delay_le_1s bigint NOT NULL, delay_1_5s bigint NOT NULL,
    delay_5_30s bigint NOT NULL, delay_gt_30s bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS hl7_transaction_daily_date
    ON mart.hl7_transaction_daily (event_day);
CREATE TABLE IF NOT EXISTS mart.integration_load_audit (
    dataset text PRIMARY KEY, source_host text NOT NULL, source_database text NOT NULL,
    source_rows bigint NOT NULL, loaded_rows bigint NOT NULL,
    undated_rows bigint NOT NULL, finished_at timestamptz NOT NULL,
    consistency_note text NOT NULL
);
