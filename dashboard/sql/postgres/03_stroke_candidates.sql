-- Supplementary prototype metadata only. No clinical text or patient identifiers.
CREATE TABLE IF NOT EXISTS mart.stroke_candidate_orders (
    order_id integer PRIMARY KEY,
    is_canceled boolean
);
CREATE TABLE IF NOT EXISTS mart.stroke_candidate_load_audit (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    source_database text NOT NULL,
    rule text NOT NULL,
    source_max_order_id integer,
    examined_orders bigint NOT NULL,
    candidate_orders bigint NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
