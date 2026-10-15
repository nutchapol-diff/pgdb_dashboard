-- Read-only source checks for the four executive widgets.
-- Database: RIS_PRARAM9 on 10.10.12.97. Run against dbo tables.
-- These queries show candidate data, not validated live KPI definitions.

-- Scanner catalog: IS_ACTIVE describes configured modality/room availability,
-- not a measured scanner uptime or downtime event.
SELECT m.MODALITY_ID, m.MODALITY_NAME, m.IS_ACTIVE AS modality_active,
       r.ROOM_NAME, r.IS_ACTIVE AS room_active, m.CASE_PER_DAY
FROM dbo.RIS_MODALITY AS m
LEFT JOIN dbo.HR_ROOM AS r ON r.ROOM_ID = m.ROOM_ID
WHERE m.MODALITY_NAME LIKE '%CT%'
ORDER BY m.MODALITY_ID;

-- Priority S and stroke-named exam candidates. The 30-minute endpoint
-- and clinical stroke cohort require a business definition.
SELECT d.PRIORITY, COUNT_BIG(*) AS stroke_named_exams,
       SUM(CASE WHEN d.IMAGE_CAPTURED_ON IS NOT NULL
                     AND DATEDIFF(MINUTE, o.ORDER_START_TIME,
                                  d.IMAGE_CAPTURED_ON) > 30
                THEN 1 ELSE 0 END) AS order_to_capture_over_30,
       SUM(CASE WHEN COALESCE(r.FIRSTFINALIZED_ON, r.FINALIZED_ON) IS NOT NULL
                     AND DATEDIFF(MINUTE, o.ORDER_START_TIME,
                                  COALESCE(r.FIRSTFINALIZED_ON, r.FINALIZED_ON)) > 30
                THEN 1 ELSE 0 END) AS order_to_report_over_30
FROM dbo.RIS_ORDERDTL AS d
JOIN dbo.RIS_EXAM AS e ON e.EXAM_ID = d.EXAM_ID
JOIN dbo.RIS_ORDER AS o ON o.ORDER_ID = d.ORDER_ID
LEFT JOIN dbo.RIS_EXAMRESULT AS r ON r.ACCESSION_NO = d.ACCESSION_NO
WHERE e.EXAM_NAME LIKE '%STROKE%'
GROUP BY d.PRIORITY
ORDER BY d.PRIORITY;

-- MRI captured/unfinalized candidates. Exclude IS_DELETED = 'Y' before
-- treating a record as active. START_ON can indicate reading has begun.
SELECT m.MODALITY_NAME, d.IS_DELETED, d.STATUS,
       COUNT_BIG(*) AS captured_unfinalized,
       SUM(CASE WHEN rt.ACCESSION_NO IS NOT NULL THEN 1 ELSE 0 END)
           AS with_read_start,
       MAX(d.IMAGE_CAPTURED_ON) AS latest_capture
FROM dbo.RIS_ORDERDTL AS d
JOIN dbo.RIS_MODALITY AS m ON m.MODALITY_ID = d.MODALITY_ID
LEFT JOIN dbo.RIS_EXAMRESULT AS r ON r.ACCESSION_NO = d.ACCESSION_NO
OUTER APPLY (
    SELECT TOP (1) t.ACCESSION_NO
    FROM dbo.RIS_EXAMRESULTTIME AS t
    WHERE t.ACCESSION_NO = d.ACCESSION_NO AND t.START_ON IS NOT NULL
) AS rt
WHERE m.MODALITY_NAME LIKE 'MR%'
  AND d.IMAGE_CAPTURED_ON IS NOT NULL
  AND r.FIRSTFINALIZED_ON IS NULL
  AND r.FINALIZED_ON IS NULL
GROUP BY m.MODALITY_NAME, d.IS_DELETED, d.STATUS
ORDER BY m.MODALITY_NAME, d.IS_DELETED, d.STATUS;

-- Arrival-to-capture coverage. This is only a possible wait proxy.
-- ARRIVAL_ON is sparse, and capture is not necessarily service start.
SELECT COUNT_BIG(*) AS exam_rows,
       COUNT_BIG(o.ARRIVAL_ON) AS arrival_rows,
       COUNT_BIG(d.IMAGE_CAPTURED_ON) AS captured_rows,
       SUM(CASE WHEN o.ARRIVAL_ON IS NOT NULL
                     AND d.IMAGE_CAPTURED_ON >= o.ARRIVAL_ON
                THEN 1 ELSE 0 END) AS usable_arrival_to_capture_rows,
       AVG(CASE WHEN o.ARRIVAL_ON IS NOT NULL
                     AND d.IMAGE_CAPTURED_ON >= o.ARRIVAL_ON
                     AND d.IMAGE_CAPTURED_ON < DATEADD(DAY, 1, o.ARRIVAL_ON)
                THEN CAST(DATEDIFF(SECOND, o.ARRIVAL_ON,
                                        d.IMAGE_CAPTURED_ON) AS float) / 60
           END) AS sampled_avg_minutes
FROM dbo.RIS_ORDERDTL AS d
JOIN dbo.RIS_ORDER AS o ON o.ORDER_ID = d.ORDER_ID;

-- Freshness of the tables used above.
SELECT (SELECT MAX(ORDER_START_TIME) FROM dbo.RIS_ORDER) AS latest_order_at,
       (SELECT MAX(LAST_MODIFIED_ON) FROM dbo.RIS_EXAMRESULT)
           AS latest_result_modified_at;
