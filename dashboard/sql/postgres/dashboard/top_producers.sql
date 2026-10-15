SELECT display_name AS "Radiologist", sum(finalized_reports)::bigint AS "Reports"
FROM mart.top_producers_daily
WHERE report_date BETWEEN %s AND %s
GROUP BY display_name ORDER BY "Reports" DESC LIMIT 10;
