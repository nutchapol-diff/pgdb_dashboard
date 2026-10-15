-- {table} is a psycopg2.sql.Identifier from the fixed dataset declarations.
CREATE TEMP TABLE stage (LIKE mart.{table}) ON COMMIT DROP;
