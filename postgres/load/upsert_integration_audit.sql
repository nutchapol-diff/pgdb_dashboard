INSERT INTO mart.integration_load_audit VALUES
    (%s,%s,%s,%s,%s,%s,clock_timestamp(),%s)
ON CONFLICT (dataset) DO UPDATE SET
    source_host=EXCLUDED.source_host, source_database=EXCLUDED.source_database,
    source_rows=EXCLUDED.source_rows, loaded_rows=EXCLUDED.loaded_rows,
    undated_rows=EXCLUDED.undated_rows, finished_at=EXCLUDED.finished_at,
    consistency_note=EXCLUDED.consistency_note;
