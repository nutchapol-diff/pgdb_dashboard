-- PROTOTYPE ONLY. All source times are interpreted as Asia/Bangkok local time.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE IF NOT EXISTS dw.dim_modality (
    modality_id integer PRIMARY KEY,
    modality_name text NOT NULL,
    modality_type integer,
    modality_type_name text,
    is_active text
);

-- Additive upgrade for existing prototype databases; populated by dimension load.
ALTER TABLE dw.dim_modality ADD COLUMN IF NOT EXISTS modality_type_name text;

CREATE TABLE IF NOT EXISTS dw.dim_exam (
    exam_id integer PRIMARY KEY,
    exam_name text NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_radiologist (
    employee_id integer PRIMARY KEY,
    display_name text NOT NULL
);

-- Grain: one RIS_ORDERDTL (ORDER_ID, EXAM_ID), located on its order date.
-- No patient identifier, accession number, or report content is copied.
CREATE TABLE IF NOT EXISTS dw.fact_exam (
    ordered_at timestamptz NOT NULL,
    order_id integer NOT NULL,
    exam_id integer NOT NULL REFERENCES dw.dim_exam(exam_id),
    modality_id integer NOT NULL REFERENCES dw.dim_modality(modality_id),
    radiologist_id integer REFERENCES dw.dim_radiologist(employee_id),
    priority_code text,
    exam_status_code text,
    result_status_code text,
    exam_at timestamptz,
    arrival_at timestamptz,
    image_captured_at timestamptz,
    qa_at timestamptz,
    first_finalized_at timestamptz,
    finalized_at timestamptz,
    released_at timestamptz,
    technical_take_count integer NOT NULL DEFAULT 0,
    source_modified_at timestamptz,
    is_deleted boolean,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ordered_at, order_id, exam_id)
);
-- Expand existing prototype databases before the transactional fact refresh.
ALTER TABLE dw.fact_exam ADD COLUMN IF NOT EXISTS is_deleted boolean;
SELECT create_hypertable('dw.fact_exam', 'ordered_at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS fact_exam_modality_time ON dw.fact_exam (modality_id, ordered_at DESC);
CREATE INDEX IF NOT EXISTS fact_exam_priority_time ON dw.fact_exam (priority_code, ordered_at DESC);
CREATE INDEX IF NOT EXISTS fact_exam_radiologist_time ON dw.fact_exam (radiologist_id, ordered_at DESC);

-- Preserve extracted rows that cannot enter the time-partitioned star.
-- No surrogate dates or dimension IDs are invented. These rows are excluded from marts.
CREATE TABLE IF NOT EXISTS dw.fact_exam_unmapped (LIKE dw.fact_exam INCLUDING DEFAULTS);
ALTER TABLE dw.fact_exam_unmapped ALTER COLUMN ordered_at DROP NOT NULL;
ALTER TABLE dw.fact_exam_unmapped ALTER COLUMN order_id DROP NOT NULL;
ALTER TABLE dw.fact_exam_unmapped ALTER COLUMN exam_id DROP NOT NULL;
ALTER TABLE dw.fact_exam_unmapped ALTER COLUMN modality_id DROP NOT NULL;

-- One row per active exam. Invalid or missing timestamp pairs produce NULL durations.
CREATE OR REPLACE VIEW mart.exam_timing AS
SELECT f.ordered_at, f.order_id, f.exam_id, f.modality_id, f.priority_code,
       f.image_captured_at, r.report_at,
       CASE WHEN f.image_captured_at >= f.ordered_at
            THEN EXTRACT(EPOCH FROM f.image_captured_at - f.ordered_at) / 60 END AS order_to_capture_min,
       CASE WHEN r.report_at >= f.image_captured_at
            THEN EXTRACT(EPOCH FROM r.report_at - f.image_captured_at) / 60 END AS capture_to_report_min,
       CASE WHEN r.report_at >= f.ordered_at
            THEN EXTRACT(EPOCH FROM r.report_at - f.ordered_at) / 60 END AS order_to_report_min,
       (f.image_captured_at < f.ordered_at) AS capture_before_order,
       (r.report_at < f.image_captured_at) AS report_before_capture,
       (r.report_at < f.ordered_at) AS report_before_order
FROM dw.fact_exam f
CROSS JOIN LATERAL (VALUES (COALESCE(f.first_finalized_at, f.finalized_at))) r(report_at)
WHERE f.is_deleted IS FALSE;

CREATE TABLE IF NOT EXISTS dw.load_audit (
    load_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    source_database text NOT NULL,
    source_exam_count bigint,
    loaded_exam_count bigint,
    source_max_order_at timestamptz,
    source_max_result_at timestamptz,
    status text NOT NULL,
    notes text
);
ALTER TABLE dw.load_audit ADD COLUMN IF NOT EXISTS unmapped_exam_count bigint NOT NULL DEFAULT 0;

-- Materialized marts are refreshed after each completed extract.
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.exam_daily AS
SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
       f.modality_id, f.priority_code,
       count(*)::bigint AS exam_count,
       count(*) FILTER (WHERE f.image_captured_at IS NOT NULL)::bigint AS captured_count,
       count(*) FILTER (WHERE f.first_finalized_at IS NOT NULL OR f.finalized_at IS NOT NULL)::bigint AS finalized_count,
       count(*) FILTER (WHERE f.first_finalized_at IS NULL AND f.finalized_at IS NULL)::bigint AS unfinalized_count,
       count(*) FILTER (WHERE f.technical_take_count > 1)::bigint AS repeat_take_count,
       count(*) FILTER (WHERE f.arrival_at IS NOT NULL)::bigint AS arrival_timestamp_count,
       percentile_cont(0.5) WITHIN GROUP (
           ORDER BY EXTRACT(EPOCH FROM (COALESCE(f.first_finalized_at, f.finalized_at) - f.ordered_at)) / 60
       ) FILTER (WHERE COALESCE(f.first_finalized_at, f.finalized_at) >= f.ordered_at) AS median_order_to_first_final_min,
       count(*) FILTER (
           WHERE COALESCE(f.first_finalized_at, f.finalized_at) > f.ordered_at + interval '4 hours'
       )::bigint AS over_four_hours_count
FROM dw.fact_exam f
GROUP BY 1, 2, 3
WITH NO DATA;
CREATE INDEX IF NOT EXISTS exam_daily_date_modality ON mart.exam_daily (order_date, modality_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.producer_daily AS
SELECT (COALESCE(f.first_finalized_at, f.finalized_at) AT TIME ZONE 'Asia/Bangkok')::date AS report_date,
       f.radiologist_id,
       count(*)::bigint AS finalized_reports
FROM dw.fact_exam f
WHERE f.radiologist_id IS NOT NULL
  AND COALESCE(f.first_finalized_at, f.finalized_at) IS NOT NULL
GROUP BY 1, 2
WITH NO DATA;
CREATE INDEX IF NOT EXISTS producer_daily_date ON mart.producer_daily (report_date, radiologist_id);

CREATE OR REPLACE VIEW mart.source_freshness AS
SELECT finished_at AS extracted_at, source_exam_count, loaded_exam_count,
       source_max_order_at, source_max_result_at,
       (now() - source_max_order_at) AS order_data_age,
       (now() - source_max_result_at) AS result_data_age
FROM dw.load_audit WHERE status = 'complete'
ORDER BY load_id DESC LIMIT 1;

CREATE OR REPLACE VIEW mart.daily_workload AS
SELECT d.order_date, m.modality_name, d.priority_code,
       d.exam_count, d.captured_count, d.finalized_count,
       d.unfinalized_count, d.repeat_take_count,
       d.median_order_to_first_final_min, d.over_four_hours_count
FROM mart.exam_daily d
JOIN dw.dim_modality m USING (modality_id);

-- This is a candidate work queue, not a verified RIS "unread" state.
CREATE OR REPLACE VIEW mart.captured_unfinalized_queue AS
SELECT m.modality_name, f.priority_code, count(*)::bigint AS exam_count,
       min(f.image_captured_at) AS oldest_capture_at
FROM dw.fact_exam f
JOIN dw.dim_modality m USING (modality_id)
WHERE f.image_captured_at IS NOT NULL
  AND f.first_finalized_at IS NULL AND f.finalized_at IS NULL
GROUP BY m.modality_name, f.priority_code;

CREATE OR REPLACE VIEW mart.top_producers AS
SELECT r.employee_id, r.display_name,
       sum(p.finalized_reports)::bigint AS finalized_reports
FROM mart.producer_daily p
JOIN dw.dim_radiologist r ON r.employee_id = p.radiologist_id
GROUP BY r.employee_id, r.display_name;

CREATE OR REPLACE VIEW mart.top_producers_daily AS
SELECT p.report_date, r.employee_id, r.display_name, p.finalized_reports
FROM mart.producer_daily p
JOIN dw.dim_radiologist r ON r.employee_id = p.radiologist_id;

CREATE OR REPLACE VIEW mart.tat_outliers_daily AS
SELECT order_date, sum(over_four_hours_count)::bigint AS over_four_hours_count
FROM mart.exam_daily GROUP BY order_date;

CREATE OR REPLACE VIEW mart.repeat_takes_by_modality AS
SELECT m.modality_name,
       count(*)::bigint AS exam_count,
       count(*) FILTER (WHERE f.technical_take_count > 1)::bigint AS multiple_take_count
FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
GROUP BY m.modality_name;

-- An order can contain multiple exams and can appear in more than one modality.
CREATE OR REPLACE VIEW mart.orders_by_modality_daily AS
SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
       m.modality_id, m.modality_name,
       count(DISTINCT f.order_id)::bigint AS order_count,
       count(*)::bigint AS exam_count
FROM dw.fact_exam f
JOIN dw.dim_modality m USING (modality_id)
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW mart.orders_by_modality AS
SELECT m.modality_id, m.modality_name,
       count(DISTINCT f.order_id)::bigint AS order_count,
       count(*)::bigint AS exam_count
FROM dw.fact_exam f
JOIN dw.dim_modality m USING (modality_id)
GROUP BY m.modality_id, m.modality_name;
