-- Parameters: page size, previous primary key, fixed maximum primary key.
WITH page AS (
    SELECT TOP (?) EXAM_RESULT_AI_ID, ACCESSION_NO, CREATED_ON,
           ABNORMALITY_SCORE, RAD_AGREED
    FROM dbo.RIS_EXAMRESULTAI
    WHERE EXAM_RESULT_AI_ID > ? AND EXAM_RESULT_AI_ID <= ?
    ORDER BY EXAM_RESULT_AI_ID
)
SELECT CAST(a.CREATED_ON AS date) AS event_day, d.MODALITY_ID,
       CASE WHEN a.ABNORMALITY_SCORE IS NULL THEN 'Missing'
            WHEN a.ABNORMALITY_SCORE < 0 OR a.ABNORMALITY_SCORE > 1 THEN 'Outside 0-1'
            WHEN a.ABNORMALITY_SCORE < .2 THEN '0.0-<0.2'
            WHEN a.ABNORMALITY_SCORE < .4 THEN '0.2-<0.4'
            WHEN a.ABNORMALITY_SCORE < .6 THEN '0.4-<0.6'
            WHEN a.ABNORMALITY_SCORE < .8 THEN '0.6-<0.8'
            ELSE '0.8-1.0' END AS score_bucket,
       COUNT_BIG(*) AS event_count, COUNT_BIG(a.ABNORMALITY_SCORE) AS score_count,
       COALESCE(SUM(CAST(a.ABNORMALITY_SCORE AS decimal(38,10))), 0) AS score_sum,
       SUM(CAST(CASE WHEN a.RAD_AGREED IN ('Y','N') THEN 1 ELSE 0 END AS bigint)) AS reviewed_count,
       SUM(CAST(CASE WHEN a.RAD_AGREED = 'Y' THEN 1 ELSE 0 END AS bigint)) AS agreed_count,
       SUM(CAST(CASE WHEN a.RAD_AGREED = 'N' THEN 1 ELSE 0 END AS bigint)) AS disagreed_count,
       MAX(a.EXAM_RESULT_AI_ID) AS page_key
FROM page a
LEFT JOIN dbo.RIS_ORDERDTL d ON d.ACCESSION_NO = a.ACCESSION_NO
GROUP BY CAST(a.CREATED_ON AS date), d.MODALITY_ID,
       CASE WHEN a.ABNORMALITY_SCORE IS NULL THEN 'Missing'
            WHEN a.ABNORMALITY_SCORE < 0 OR a.ABNORMALITY_SCORE > 1 THEN 'Outside 0-1'
            WHEN a.ABNORMALITY_SCORE < .2 THEN '0.0-<0.2'
            WHEN a.ABNORMALITY_SCORE < .4 THEN '0.2-<0.4'
            WHEN a.ABNORMALITY_SCORE < .6 THEN '0.4-<0.6'
            WHEN a.ABNORMALITY_SCORE < .8 THEN '0.6-<0.8'
            ELSE '0.8-1.0' END
OPTION (RECOMPILE);
