SELECT source_database FROM dw.load_audit
WHERE status = 'complete' ORDER BY load_id DESC LIMIT 1;
