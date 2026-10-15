INSERT INTO dw.dim_modality (modality_id, modality_name, modality_type, is_active, modality_type_name)
VALUES %s ON CONFLICT (modality_id) DO UPDATE SET
  modality_name=EXCLUDED.modality_name, modality_type=EXCLUDED.modality_type,
  is_active=EXCLUDED.is_active, modality_type_name=EXCLUDED.modality_type_name;
