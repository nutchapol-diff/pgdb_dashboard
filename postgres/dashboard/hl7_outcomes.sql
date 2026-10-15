SELECT COALESCE(NULLIF(trim(status_code),''),'No status') AS status_code,
       COALESCE(NULLIF(trim(ack_code),''),'No ACK code') AS ack_code,
       sum(event_count)::bigint AS log_records
FROM mart.hl7_ie_daily
WHERE event_day BETWEEN %s AND %s AND COALESCE(is_deleted,'') <> 'Y'
GROUP BY status_code, ack_code ORDER BY status_code, ack_code;
