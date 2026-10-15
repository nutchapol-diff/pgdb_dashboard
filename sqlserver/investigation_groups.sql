-- HN and VISIT_NO are used only inside SQL Server; never returned or copied.
-- SERVICE_TYPE_ID=1 / SERVICE_TYPE_UID='1' is Investigation in RIS_CU.
WITH eligible AS (
 SELECT d.ORDER_ID, d.EXAM_ID, d.MODALITY_ID, CAST(o.ORDER_START_TIME AS date) AS order_day,
        o.ORG_ID,
        CASE WHEN NULLIF(LTRIM(RTRIM(o.HN)), '') IS NULL
             THEN CONCAT('missing:', o.ORDER_ID) ELSE CONCAT('patient:', LTRIM(RTRIM(o.HN))) END AS patient_key,
        CASE WHEN NULLIF(LTRIM(RTRIM(o.VISIT_NO)), '') IS NULL
             THEN CONCAT('missing:', o.ORDER_ID) ELSE CONCAT('visit:', LTRIM(RTRIM(o.VISIT_NO))) END AS visit_key,
        CASE WHEN NULLIF(LTRIM(RTRIM(o.HN)), '') IS NULL THEN 0 ELSE 1 END AS patient_known,
        CASE WHEN NULLIF(LTRIM(RTRIM(o.VISIT_NO)), '') IS NULL THEN 0 ELSE 1 END AS visit_known,
        CASE WHEN d.IMAGE_CAPTURED_ON IS NOT NULL THEN 1 ELSE 0 END AS captured,
        CASE WHEN d.SERVICE_TYPE=1 THEN 1 ELSE 0 END AS detail_service
 FROM dbo.RIS_ORDERDTL d
 JOIN dbo.RIS_ORDER o ON o.ORDER_ID=d.ORDER_ID
 JOIN dbo.RIS_EXAM e ON e.EXAM_ID=d.EXAM_ID
 WHERE (d.SERVICE_TYPE=1 OR (d.SERVICE_TYPE IS NULL AND e.SERVICE_TYPE='1'))
   AND COALESCE(d.IS_DELETED,'') <> 'Y'
   AND COALESCE(o.IS_CANCELED,'') <> 'Y' AND o.ORDER_START_TIME IS NOT NULL
), grouped AS (
 SELECT CASE WHEN GROUPING(visit_key)=0 THEN 'same_visit' ELSE 'same_day' END AS match_rule,
        order_day, MIN(ORDER_ID) AS anchor_order_id, EXAM_ID, MODALITY_ID,
        COUNT_BIG(*) AS exam_records, SUM(CAST(captured AS bigint)) AS captured_exams,
        SUM(CAST(detail_service AS bigint)) AS detail_service_exams,
        CASE WHEN GROUPING(visit_key)=0 THEN MIN(patient_known)*MIN(visit_known)
             ELSE MIN(patient_known) END AS matching_keys_complete
 FROM eligible
 GROUP BY GROUPING SETS (
   (ORG_ID,patient_key,order_day,EXAM_ID,MODALITY_ID,visit_key),
   (ORG_ID,patient_key,order_day,EXAM_ID,MODALITY_ID)
 )
)
SELECT match_rule,order_day,anchor_order_id,EXAM_ID,MODALITY_ID,
       exam_records,captured_exams,matching_keys_complete,
       CASE WHEN exam_records>1 AND captured_exams>0 AND matching_keys_complete=1
            THEN exam_records-captured_exams ELSE CAST(0 AS bigint) END AS suspected_uncaptured,
       detail_service_exams,exam_records-detail_service_exams AS definition_service_exams
FROM grouped;
