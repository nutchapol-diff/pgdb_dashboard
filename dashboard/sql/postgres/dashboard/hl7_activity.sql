-- Interface logs have no validated modality attribution. Exclude soft-deleted logs.
SELECT event_day, COALESCE(NULLIF(trim(ack_code),''),'No ACK code') AS ack_code,
       sum(event_count)::bigint AS log_records
FROM mart.hl7_ie_daily
WHERE event_day BETWEEN %s AND %s AND COALESCE(is_deleted,'') <> 'Y'
GROUP BY event_day, COALESCE(NULLIF(trim(ack_code),''),'No ACK code')
ORDER BY event_day, ack_code;
