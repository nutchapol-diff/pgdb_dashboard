SELECT dataset, source_database, source_rows AS source_records,
       loaded_rows AS loaded_records, 0::bigint AS excluded_records,
       undated_rows AS undated_records, finished_at, consistency_note
FROM mart.integration_load_audit ORDER BY dataset;
