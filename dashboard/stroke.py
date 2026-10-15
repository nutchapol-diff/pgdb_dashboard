"""Read-only access to separately loaded stroke mention candidates."""


def get_stroke_summary(query, sql, where, params, source_database):
    ready = query("SELECT to_regclass('mart.stroke_candidate_load_audit') IS NOT NULL AS ready").iloc[0]['ready']
    if not ready:
        return None, None
    audit = query('SELECT * FROM mart.stroke_candidate_load_audit')
    if audit.empty or audit.iloc[0]['source_database'] != source_database:
        return None, None
    return query(sql('stroke_summary.sql', where), params).iloc[0], audit.iloc[0]
