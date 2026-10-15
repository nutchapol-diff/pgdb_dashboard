-- Same population as daily.sql: all deletion flags, valid order-to-first-final
-- intervals, selected order dates/modality. Compute exact quartiles in PostgreSQL.
-- Summarize both outlier tails using the same daily fences; absent means are NULL.
WITH durations AS (
    SELECT (f.ordered_at AT TIME ZONE 'Asia/Bangkok')::date AS order_date,
           EXTRACT(EPOCH FROM (COALESCE(f.first_finalized_at,f.finalized_at)
                              - f.ordered_at)) / 60 AS tat_min
    FROM dw.fact_exam f JOIN dw.dim_modality m USING (modality_id)
    WHERE {where}
      AND COALESCE(f.first_finalized_at,f.finalized_at) >= f.ordered_at
), quartiles AS (
    SELECT order_date, count(*)::bigint AS valid_samples,
           percentile_cont(ARRAY[0.25,0.5,0.75]) WITHIN GROUP (ORDER BY tat_min) AS q
    FROM durations GROUP BY order_date
), fences AS (
    SELECT *, q[1] - 1.5 * (q[3]-q[1]) AS lower_cutoff_min,
              q[3] + 1.5 * (q[3]-q[1]) AS upper_cutoff_min
    FROM quartiles
)
SELECT s.order_date, s.valid_samples,
       avg(d.tat_min) AS mean_min,
       s.q[1] AS q1_min, s.q[2] AS median_min, s.q[3] AS q3_min,
       s.q[3]-s.q[1] AS iqr_min, s.lower_cutoff_min, s.upper_cutoff_min,
       min(d.tat_min) FILTER (WHERE d.tat_min BETWEEN s.lower_cutoff_min AND s.upper_cutoff_min) AS lower_whisker_min,
       max(d.tat_min) FILTER (WHERE d.tat_min BETWEEN s.lower_cutoff_min AND s.upper_cutoff_min) AS upper_whisker_min,
       count(*) FILTER (WHERE d.tat_min < s.lower_cutoff_min OR d.tat_min > s.upper_cutoff_min)::bigint AS iqr_outliers,
       avg(d.tat_min) FILTER (WHERE d.tat_min < s.lower_cutoff_min) AS low_outlier_mean_min,
       avg(d.tat_min) FILTER (WHERE d.tat_min > s.upper_cutoff_min) AS high_outlier_mean_min,
       avg(d.tat_min) FILTER (WHERE d.tat_min BETWEEN s.lower_cutoff_min AND s.upper_cutoff_min) AS normal_mean_min,
       count(*) FILTER (WHERE d.tat_min BETWEEN s.lower_cutoff_min AND s.upper_cutoff_min)::bigint AS normal_count,
       count(*) FILTER (WHERE d.tat_min < s.lower_cutoff_min)::bigint AS low_outlier_count,
       count(*) FILTER (WHERE d.tat_min > s.upper_cutoff_min)::bigint AS high_outlier_count,
       count(*) FILTER (WHERE d.tat_min > 240)::bigint AS over_four_hours
FROM fences s JOIN durations d USING (order_date)
GROUP BY s.order_date, s.valid_samples, s.q, s.lower_cutoff_min, s.upper_cutoff_min
ORDER BY s.order_date;
