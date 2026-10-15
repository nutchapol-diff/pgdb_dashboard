DELETE FROM mart.stroke_candidate_orders;
INSERT INTO mart.stroke_candidate_orders SELECT * FROM stroke_stage;
