-- Stream all linked workflow logs once, bounded by initial maximum detail order.
-- Accession and clinical text remain inside this source query.
SELECT d.ORDER_ID, d.EXAM_ID, tw.START_TIME, tw.END_TIME
FROM dbo.RIS_TECHWORKS tw
JOIN dbo.RIS_ORDERDTL d ON d.ACCESSION_NO = tw.ACCESSION_NO
WHERE d.ORDER_ID <= ?
OPTION (RECOMPILE);
