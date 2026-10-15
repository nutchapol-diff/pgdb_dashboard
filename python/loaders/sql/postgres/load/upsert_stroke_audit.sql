INSERT INTO mart.stroke_candidate_load_audit
    (singleton, source_database, rule, source_max_order_id, examined_orders, candidate_orders)
VALUES (true, %s, %s, %s, %s, %s)
ON CONFLICT (singleton) DO UPDATE SET
    source_database=EXCLUDED.source_database, rule=EXCLUDED.rule,
    source_max_order_id=EXCLUDED.source_max_order_id,
    examined_orders=EXCLUDED.examined_orders, candidate_orders=EXCLUDED.candidate_orders,
    loaded_at=now();
