-- Read-only supplement. Do not infer cancellation from RIS_ORDERDTL.STATUS.
SELECT ORDER_ID FROM dbo.RIS_ORDER WHERE IS_CANCELED = 'Y' ORDER BY ORDER_ID;
