INSERT INTO dw.dim_radiologist (employee_id, display_name) VALUES %s
ON CONFLICT (employee_id) DO UPDATE SET display_name=EXCLUDED.display_name;
