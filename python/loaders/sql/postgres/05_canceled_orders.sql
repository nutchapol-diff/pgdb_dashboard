-- Keep the original exam extract; cancellation is supplementary order metadata.
CREATE TABLE IF NOT EXISTS mart.canceled_orders (order_id integer PRIMARY KEY);
CREATE TABLE IF NOT EXISTS mart.canceled_order_load_audit (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    source_database text NOT NULL,
    canceled_orders bigint NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
