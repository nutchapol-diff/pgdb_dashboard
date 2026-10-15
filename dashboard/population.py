"""Shared RIS Snapshot population for cards, graphs and Data Explorer."""
import pandas as pd


def snapshot_filters(query, source_database, fact_where, joined_where):
    ready = query("SELECT to_regclass('mart.canceled_order_load_audit') IS NOT NULL AS ready").iloc[0]['ready']
    audit = query('SELECT * FROM mart.canceled_order_load_audit') if ready else pd.DataFrame()
    if audit.empty or audit.iloc[0]['source_database'] != source_database:
        raise ValueError('Cancellation metadata is unavailable for this source. Run load_canceled_orders.py before viewing RIS Snapshot.')
    predicate = (' AND f.is_deleted IS NOT TRUE AND NOT EXISTS '
                 '(SELECT 1 FROM mart.canceled_orders canceled WHERE canceled.order_id = f.order_id)')
    return fact_where + predicate, joined_where + predicate, audit
