-- Read-only exploration for RIS_CU. Run with RIS_CU selected.
-- This bounded sample proves candidate data exists; it is NOT a full-history KPI.
-- Text mentions can include history, exclusion, or suspected stroke.
-- Priority S and the KPI endpoints require hospital confirmation.
-- No clinical text or patient identifiers are returned.
DECLARE @SampleOrderCount int = 20000;

WITH recent AS (
    SELECT TOP (@SampleOrderCount)
           ORDER_ID, ORDER_START_TIME, IS_CANCELED, CLINICAL_INSTRUCTION
    FROM dbo.RIS_ORDER
    ORDER BY ORDER_ID DESC
), candidates AS (
    SELECT ORDER_ID, ORDER_START_TIME, IS_CANCELED
    FROM recent
    WHERE CLINICAL_INSTRUCTION LIKE '%stroke%'
)
SELECT d.PRIORITY,
       COUNT_BIG(*) AS candidate_exam_rows,
       SUM(CASE WHEN d.IS_DELETED = 'N'
                     AND COALESCE(o.IS_CANCELED, 'N') = 'N'
                THEN 1 ELSE 0 END) AS nondeleted_noncancelled,
       SUM(CASE WHEN d.IS_DELETED = 'N'
                     AND COALESCE(o.IS_CANCELED, 'N') = 'N'
                     AND d.IMAGE_CAPTURED_ON > DATEADD(MINUTE, 30, o.ORDER_START_TIME)
                THEN 1 ELSE 0 END) AS order_to_capture_over_30,
       SUM(CASE WHEN d.IS_DELETED = 'N'
                     AND COALESCE(o.IS_CANCELED, 'N') = 'N'
                     AND COALESCE(r.FIRSTFINALIZED_ON, r.FINALIZED_ON)
                         > DATEADD(MINUTE, 30, o.ORDER_START_TIME)
                THEN 1 ELSE 0 END) AS order_to_first_final_over_30,
       SUM(CASE WHEN d.IS_DELETED = 'N'
                     AND COALESCE(o.IS_CANCELED, 'N') = 'N'
                     AND COALESCE(r.FIRSTFINALIZED_ON, r.FINALIZED_ON) IS NULL
                THEN 1 ELSE 0 END) AS no_final,
       MIN(o.ORDER_START_TIME) AS first_candidate_order,
       MAX(o.ORDER_START_TIME) AS last_candidate_order
FROM candidates o
JOIN dbo.RIS_ORDERDTL d ON d.ORDER_ID = o.ORDER_ID
LEFT JOIN dbo.RIS_EXAMRESULT r ON r.ACCESSION_NO = d.ACCESSION_NO
GROUP BY d.PRIORITY
ORDER BY d.PRIORITY
OPTION (RECOMPILE);
