-- Metadata backfill only; does not reload facts or change source type IDs.
UPDATE dw.dim_modality SET modality_type_name = %s WHERE modality_type = %s;
