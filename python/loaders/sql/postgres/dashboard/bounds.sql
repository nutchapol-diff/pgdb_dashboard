SELECT min(order_date) AS first_day, max(order_date) AS last_day,
       max(order_date) FILTER (WHERE daily_exams >= 50) AS last_complete_day
FROM (SELECT order_date, sum(exam_count) AS daily_exams
      FROM mart.exam_daily GROUP BY order_date) days;
