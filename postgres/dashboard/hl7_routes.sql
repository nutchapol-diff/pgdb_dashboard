SELECT COALESCE(NULLIF(sender,''),'Unknown sender') AS sender,
       COALESCE(NULLIF(receiver,''),'Unknown receiver') AS receiver,
       COALESCE(NULLIF(message_type,''),'Unknown type') AS message_type,
       sum(event_count)::bigint AS log_records,
       sum(event_count) FILTER (WHERE NULLIF(trim(ack_code),'') IS NOT NULL)::bigint AS with_ack_code
FROM mart.hl7_ie_daily
WHERE event_day BETWEEN %s AND %s AND COALESCE(is_deleted,'') <> 'Y'
GROUP BY sender, receiver, message_type ORDER BY log_records DESC LIMIT 20;
