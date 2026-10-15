SELECT dataset, source_host, source_database, source_rows, loaded_rows,
       undated_rows, finished_at, consistency_note
FROM mart.integration_load_audit ORDER BY dataset;
