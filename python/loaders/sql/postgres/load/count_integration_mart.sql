SELECT COALESCE(sum(event_count),0),
       COALESCE(sum(event_count) FILTER (WHERE event_day IS NULL),0)
FROM mart.{table};
