-- Preserve source type IDs; do not infer type from scanner names.
SELECT modality_type,
       COALESCE(min(NULLIF(modality_type_name, '')),
                CASE WHEN modality_type IS NULL THEN 'Unknown modality type'
                     ELSE 'Type ' || modality_type::text END) AS modality_type_name
FROM dw.dim_modality
GROUP BY modality_type
ORDER BY modality_type_name, modality_type;
