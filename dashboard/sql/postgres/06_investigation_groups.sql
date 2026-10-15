-- One group per rule + patient(/visit) + Bangkok day + exam + modality + source organization.
-- Patient/visit identities are not retained. Anchor is the minimum source order ID,
-- not a confirmed clinical investigation identifier.
CREATE TABLE IF NOT EXISTS mart.investigation_groups (
 match_rule text NOT NULL CHECK (match_rule IN ('same_visit','same_day')),
 order_day date NOT NULL,
 anchor_order_id integer NOT NULL,
 exam_id integer NOT NULL,
 modality_id integer,
 exam_records bigint NOT NULL CHECK (exam_records > 0),
 captured_exams bigint NOT NULL CHECK (captured_exams BETWEEN 0 AND exam_records),
 matching_keys_complete boolean NOT NULL,
 suspected_uncaptured bigint NOT NULL CHECK (suspected_uncaptured BETWEEN 0 AND exam_records-captured_exams),
 detail_service_exams bigint NOT NULL DEFAULT 0,
 definition_service_exams bigint NOT NULL DEFAULT 0,
 PRIMARY KEY (match_rule,order_day,anchor_order_id,exam_id)
);
-- Remove the unused report count from this task's initial intermediate schema.
ALTER TABLE mart.investigation_groups DROP COLUMN IF EXISTS finalized_exams;
ALTER TABLE mart.investigation_groups ADD COLUMN IF NOT EXISTS detail_service_exams bigint NOT NULL DEFAULT 0;
ALTER TABLE mart.investigation_groups ADD COLUMN IF NOT EXISTS definition_service_exams bigint NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS investigation_groups_modality_day ON mart.investigation_groups (modality_id,order_day);
CREATE TABLE IF NOT EXISTS mart.investigation_group_load_audit (
 singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
 source_database text NOT NULL,
 group_rows bigint NOT NULL,
 investigation_exams bigint NOT NULL,
 loaded_at timestamptz NOT NULL DEFAULT now()
);
