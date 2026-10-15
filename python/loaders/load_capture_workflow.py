"""Read-only full-history TECHWORKS summary refresh. Same connection env as load.py."""
import argparse
import io
import os
import pyodbc
import psycopg2
from load import sql, copy_field, local_time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-database',default='RIS_CU')
    parser.add_argument('--target-database',default='radops_cu_prototype')
    args=parser.parse_args()
    if not args.source_database.replace('_','').isalnum():
        raise ValueError('Unsafe source database identifier')
    source=pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
        f"SERVER={os.getenv('SRC_MSSQL_HOST','10.10.12.97')},{os.getenv('SRC_MSSQL_PORT','1433')};"
        f'DATABASE={args.source_database};'
        f"UID={os.environ['SRC_MSSQL_USER']};PWD={os.environ['SRC_MSSQL_PASSWORD']};"
        'Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;',timeout=10,autocommit=True)
    source.timeout=90
    try:
        target=psycopg2.connect(host=os.getenv('PGHOST','127.0.0.1'),port=os.getenv('PGPORT','6543'),
            dbname=args.target_database,user=os.getenv('PGUSER','postgres'),password=os.environ['PGPASSWORD'])
        try:
            with target:
                src,dst=source.cursor(),target.cursor()
                dst.execute("SELECT pg_advisory_xact_lock(hashtext('radops_capture_workflow'))")
                dst.execute(sql('postgres/04_capture_workflow.sql'))
                dst.execute('CREATE TEMP TABLE capture_stage (LIKE mart.capture_workflow INCLUDING ALL) ON COMMIT DROP')
                dst.execute('CREATE TEMP TABLE capture_logs (order_id integer,exam_id integer,started_at timestamptz,ended_at timestamptz) ON COMMIT DROP')
                src.execute('SELECT MAX(ORDER_ID) FROM dbo.RIS_ORDERDTL')
                maximum=src.fetchone()[0]
                copied=0
                if maximum is not None:
                    src.execute(sql('sqlserver/techworks_workflow_page.sql'),(maximum,))
                    while batch:=src.fetchmany(10000):
                        buffer=io.StringIO()
                        for row in batch:
                            buffer.write('\t'.join(copy_field(local_time(v) if i in (2,3) else v) for i,v in enumerate(row))+'\n')
                        buffer.seek(0)
                        dst.copy_expert('COPY capture_logs FROM STDIN WITH (FORMAT text)',buffer)
                        copied+=len(batch)
                        if copied % 100000 == 0:
                            print(f'{copied:,} linked workflow logs staged',flush=True)
                dst.execute(sql('postgres/load/aggregate_capture_workflow.sql'))
                dst.execute('SELECT count(*),COALESCE(sum(log_entries),0) FROM capture_stage')
                count,represented=dst.fetchone()
                if represented!=copied:
                    raise RuntimeError('Workflow stage count mismatch')
                dst.execute(sql('postgres/load/replace_capture_workflow.sql'),(args.source_database,maximum,count))
            print(f'Committed {count:,} workflow exam summaries.',flush=True)
        finally:
            target.close()
    finally:
        source.close()


if __name__=='__main__':
    main()
