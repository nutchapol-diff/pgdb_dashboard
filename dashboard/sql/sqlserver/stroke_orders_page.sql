-- Bounded numeric PK range. Both result sets cover the same range.
-- Clinical text is evaluated at source and never returned.
SELECT COUNT_BIG(*) FROM dbo.RIS_ORDER WHERE ORDER_ID >= ? AND ORDER_ID <= ?;
SELECT ORDER_ID,
       CASE IS_CANCELED WHEN 'Y' THEN 1 WHEN 'N' THEN 0 END AS is_canceled
FROM dbo.RIS_ORDER
WHERE ORDER_ID >= ? AND ORDER_ID <= ?
  AND CLINICAL_INSTRUCTION LIKE '%stroke%'
ORDER BY ORDER_ID;
