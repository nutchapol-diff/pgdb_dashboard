"""PROTOTYPE: rebuild the selected RIS exam star from read-only queries.

Required environment: SRC_MSSQL_USER, SRC_MSSQL_PASSWORD, PGPASSWORD.
Optional connections: SRC_MSSQL_HOST, PGHOST, PGPORT, PGUSER.
Select databases using --source-database and --target-database.
No patient identifier, accession number, or report body is written to Postgres.
"""

import argparse
import io
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import execute_values
import pyodbc


TZ = ZoneInfo("Asia/Bangkok")
ROOT = Path(__file__).parent
SQL_DIR = ROOT / "sql"
LOCAL_TIME_COLUMNS = {0, 8, 9, 10, 11, 12, 13, 14, 16}
COPY_BATCH_SIZE = 10_000
SOURCE_PAGE_SIZE = 20_000


def sql(path):
    return (SQL_DIR / path).read_text(encoding="utf-8")


def local_time(value):
    return value.replace(tzinfo=TZ) if value is not None else None


def copy_field(value):
    if value is None:
        return r"\N"
    if not isinstance(value, str):
        return str(value)
    return (value.replace("\\", "\\\\").replace("\t", r"\t")
            .replace("\n", r"\n").replace("\r", r"\r"))


def copy_rows(cursor, rows, statement):
    data = io.StringIO()
    for row in rows:
        data.write("\t".join(copy_field(local_time(value) if i in LOCAL_TIME_COLUMNS else value)
                             for i, value in enumerate(row)))
        data.write("\n")
    data.seek(0)
    cursor.copy_expert(statement, data)


def fetch_all(cursor, query):
    cursor.execute(query)
    rows = []
    while batch := cursor.fetchmany(2000):
        rows.extend(tuple(row) for row in batch)
    return rows


def fact_batches(cursor):
    """Read all joined details in bounded pages using the source composite PK."""
    cursor.execute(sql("sqlserver/fact_key_bounds.sql"))
    minimum, maximum = cursor.fetchone()
    if minimum is None:
        return
    last_order, last_exam = minimum - 1, 0
    statement = sql("sqlserver/fact_exam_extract.sql")
    while True:
        cursor.execute(statement, (SOURCE_PAGE_SIZE, last_order, last_order, last_exam, maximum))
        page_count = 0
        while batch := cursor.fetchmany(2000):
            page_count += len(batch)
            last_order, last_exam = batch[-1][1], batch[-1][2]
            yield batch
        if page_count < SOURCE_PAGE_SIZE:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-database", default="RIS_CU")
    parser.add_argument("--target-database", default="radops_cu_prototype")
    args = parser.parse_args()
    source_host = os.getenv("SRC_MSSQL_HOST", "10.10.12.97")
    source_db = args.source_database
    if not source_db.replace("_", "").isalnum():
        raise ValueError("Source database must contain only letters, digits, and underscores")
    source = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={source_host},1433;DATABASE={source_db};"
        f"UID={os.environ['SRC_MSSQL_USER']};PWD={os.environ['SRC_MSSQL_PASSWORD']};"
        "Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;",
        timeout=10,
        autocommit=True,
    )
    target = psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "6543"),
        dbname=args.target_database,
        user=os.getenv("PGUSER", "postgres"),
        password=os.environ["PGPASSWORD"],
    )
    try:
        src = source.cursor()
        dst = target.cursor()
        dst.execute(sql("postgres/01_schema.sql"))

        src.execute(sql("sqlserver/source_count_and_max_order.sql"))
        source_count, max_order = src.fetchone()
        print(f"Extracting {source_count:,} exam rows from {source_host}/{source_db}", flush=True)
        src.execute(sql("sqlserver/max_result.sql"))
        max_result = src.fetchone()[0]

        modalities = fetch_all(src, sql("sqlserver/modalities.sql"))
        execute_values(dst, sql("postgres/load/upsert_modality.sql"), modalities)

        exams = fetch_all(src, sql("sqlserver/exams.sql"))
        execute_values(dst, sql("postgres/load/upsert_exam.sql"), exams)

        radiologists = fetch_all(src, sql("sqlserver/radiologists.sql"))
        if radiologists:
            execute_values(dst, sql("postgres/load/upsert_radiologist.sql"), radiologists)

        dst.execute(sql("postgres/load/clear_fact.sql"))
        dst.execute(sql("postgres/load/clear_unmapped.sql"))
        inserted = 0
        unmapped = 0
        next_progress = 100_000
        copy_sql = sql("postgres/load/copy_fact.sql")
        unmapped_sql = sql("postgres/load/copy_unmapped.sql")
        copy_buffer = []
        for batch in fact_batches(src):
            invalid = [row for row in batch if any(row[i] is None for i in (0, 1, 2, 3))]
            if invalid:
                copy_rows(dst, invalid, unmapped_sql)
                unmapped += len(invalid)
            copy_buffer.extend(row for row in batch if all(row[i] is not None for i in (0, 1, 2, 3)))
            if len(copy_buffer) >= COPY_BATCH_SIZE:
                copy_rows(dst, copy_buffer, copy_sql)
                inserted += len(copy_buffer)
                copy_buffer.clear()
                if inserted + unmapped >= next_progress:
                    print(f"Copied {inserted:,} star rows; {unmapped:,} unmapped", flush=True)
                    next_progress = inserted + unmapped + 100_000
        if copy_buffer:
            copy_rows(dst, copy_buffer, copy_sql)
            inserted += len(copy_buffer)
        if inserted + unmapped != source_count:
            raise RuntimeError(f"Source/extract row count mismatch: {source_count} vs {inserted + unmapped}")
        dst.execute(sql("postgres/load/count_fact.sql"))
        if dst.fetchone()[0] != inserted:
            raise RuntimeError("Database fact count failed validation")
        dst.execute(sql("postgres/load/count_unmapped.sql"))
        if dst.fetchone()[0] != unmapped:
            raise RuntimeError("Database unmapped count failed validation")

        dst.execute(sql("postgres/load/analyze_warehouse.sql"))
        dst.execute(sql("postgres/load/refresh_exam_daily.sql"))
        dst.execute(sql("postgres/load/refresh_producer_daily.sql"))
        dst.execute(sql("postgres/load/analyze_marts.sql"))
        dst.execute(sql("postgres/load/insert_load_audit.sql"),
                    (source_db, source_count, inserted, local_time(max_order), local_time(max_result), unmapped))
        target.commit()
        print(f"Loaded {inserted} star exams and {unmapped} unmapped exams from {source_db} into {args.target_database}")
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()
        source.close()


if __name__ == "__main__":
    main()
