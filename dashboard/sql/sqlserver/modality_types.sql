-- Read-only label lookup used to backfill the existing prototype dimension.
SELECT TYPE_ID, NULLIF(LTRIM(RTRIM(TYPE_NAME)), '') AS TYPE_NAME
FROM dbo.RIS_MODALITYTYPE;
