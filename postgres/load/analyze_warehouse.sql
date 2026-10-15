-- Refresh planner statistics after the fact rebuild and before mart refreshes.
ANALYZE dw.dim_modality;
ANALYZE dw.dim_exam;
ANALYZE dw.dim_radiologist;
ANALYZE dw.fact_exam;
