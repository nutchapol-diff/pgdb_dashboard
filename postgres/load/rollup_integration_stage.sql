-- Dimensions and measures are trusted SQL fragments from DATASETS, not runtime input.
INSERT INTO mart.{table}
SELECT {dimensions}, {measures} FROM stage GROUP BY {dimensions};
