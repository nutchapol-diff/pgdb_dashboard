"""Publish full-history investigation matching groups without patient identifiers.

Uses the connection environment of load.py. Source is read-only; replacement
and audit commit atomically. This separate refresh is not CDC or a synchronized
snapshot of the exam star. No source orders are deleted or modified.
"""
import argparse
from contextlib import closing
import io
import os
from pathlib import Path

import psycopg2
import pyodbc

ROOT = Path(__file__).parent / 'sql'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-database', default='RIS_CU')
    parser.add_argument('--target-database', default='radops_cu_prototype')
    args = parser.parse_args()
    if not args.source_database.replace('_', '').isalnum():
        raise ValueError('Invalid source database name')
    with closing(pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        f"SERVER={os.getenv('SRC_MSSQL_HOST','10.10.12.97')},1433;DATABASE={args.source_database};"
        f"UID={os.environ['SRC_MSSQL_USER']};PWD={os.environ['SRC_MSSQL_PASSWORD']};"
        'Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;', timeout=10,autocommit=True)) as source:
        source.timeout = 1800
        src = source.cursor()
        src.execute("SELECT SERVICE_TYPE_UID,SERVICE_TYPE_TEXT FROM dbo.RIS_SERVICETYPE WHERE SERVICE_TYPE_ID=1")
        service = src.fetchone()
        if service is None or str(service[0]).strip() != '1' or str(service[1]).strip().lower() != 'investigation':
            raise ValueError('Service type 1 is not confirmed as Investigation for this source')
        with closing(psycopg2.connect(host=os.getenv('PGHOST','127.0.0.1'),port=os.getenv('PGPORT','6543'),
                     dbname=args.target_database,user=os.getenv('PGUSER','postgres'),
                     password=os.environ['PGPASSWORD'],connect_timeout=10)) as target:
            with target.cursor() as dst:
                dst.execute("SELECT pg_advisory_xact_lock(hashtext('radops_investigation_groups'))")
                dst.execute((ROOT/'postgres/06_investigation_groups.sql').read_text())
                dst.execute('CREATE TEMP TABLE investigation_stage (LIKE mart.investigation_groups INCLUDING ALL) ON COMMIT DROP')
                print('Grouping full-history Investigation orders at SQL Server; only anonymous group summaries will be copied.',flush=True)
                src.execute((ROOT/'sqlserver/investigation_groups.sql').read_text())
                copied=0
                while batch := src.fetchmany(2000):
                    buffer=io.StringIO()
                    for row in batch:
                        fields=[str(v) if v is not None else r'\N' for v in row]
                        fields[7]='true' if row[7] else 'false'
                        buffer.write('\t'.join(fields)+'\n')
                    buffer.seek(0)
                    dst.copy_expert('COPY investigation_stage FROM STDIN',buffer)
                    copied+=len(batch)
                    if copied % 100000 == 0:
                        print(f'Copied {copied:,} anonymous matching groups.',flush=True)
                dst.execute('SELECT count(*) FROM investigation_stage')
                if dst.fetchone()[0]!=copied:
                    raise RuntimeError('Stage count mismatch')
                dst.execute('SELECT match_rule,sum(exam_records),sum(captured_exams) FROM investigation_stage GROUP BY match_rule ORDER BY match_rule')
                totals=dst.fetchall()
                if len(totals)!=2 or totals[0][1:]!=totals[1][1:]:
                    raise RuntimeError('Matching rules do not cover the same source investigation population')
                dst.execute('DELETE FROM mart.investigation_groups')
                dst.execute('INSERT INTO mart.investigation_groups SELECT * FROM investigation_stage')
                dst.execute('''INSERT INTO mart.investigation_group_load_audit (source_database,group_rows,investigation_exams)
                    VALUES (%s,%s,%s) ON CONFLICT (singleton) DO UPDATE SET
                    source_database=EXCLUDED.source_database,group_rows=EXCLUDED.group_rows,
                    investigation_exams=EXCLUDED.investigation_exams,loaded_at=now()''',
                    (args.source_database,copied,int(totals[0][1])))
                dst.execute('ANALYZE mart.investigation_groups')
            target.commit()
        print(f'Published {copied:,} groups, covering {int(totals[0][1]):,} investigation exam records per rule.',flush=True)


if __name__=='__main__':
    main()
