"""Read explicit RIS order cancellations and publish atomically.

Same connection environment as load.py. No source writes or patient data.
This independent historical refresh is not a synchronized source snapshot.
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
    source = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        f"SERVER={os.getenv('SRC_MSSQL_HOST', '10.10.12.97')},1433;"
        f'DATABASE={args.source_database};'
        f"UID={os.environ['SRC_MSSQL_USER']};PWD={os.environ['SRC_MSSQL_PASSWORD']};"
        'Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;',
        timeout=10, autocommit=True)
    source.timeout = 120
    try:
        with closing(psycopg2.connect(host=os.getenv('PGHOST', '127.0.0.1'),
                              port=os.getenv('PGPORT', '6543'),
                              dbname=args.target_database, user=os.getenv('PGUSER', 'postgres'),
                              password=os.environ['PGPASSWORD'], connect_timeout=10)) as target:
            with target.cursor() as dst:
                dst.execute("SELECT pg_advisory_xact_lock(hashtext('radops_canceled_orders'))")
                dst.execute((ROOT / 'postgres/05_canceled_orders.sql').read_text())
                dst.execute('CREATE TEMP TABLE canceled_stage (LIKE mart.canceled_orders INCLUDING ALL) ON COMMIT DROP')
                src = source.cursor()
                src.execute((ROOT / 'sqlserver/canceled_orders.sql').read_text())
                copied = 0
                while batch := src.fetchmany(2000):
                    buffer = io.StringIO(''.join(f'{row[0]}\n' for row in batch))
                    dst.copy_expert('COPY canceled_stage (order_id) FROM STDIN', buffer)
                    copied += len(batch)
                dst.execute('SELECT count(*) FROM canceled_stage')
                if dst.fetchone()[0] != copied:
                    raise RuntimeError('Cancellation stage count mismatch')
                dst.execute('DELETE FROM mart.canceled_orders')
                dst.execute('INSERT INTO mart.canceled_orders SELECT order_id FROM canceled_stage')
                dst.execute('''INSERT INTO mart.canceled_order_load_audit (source_database,canceled_orders)
                    VALUES (%s,%s) ON CONFLICT (singleton) DO UPDATE SET
                    source_database=EXCLUDED.source_database, canceled_orders=EXCLUDED.canceled_orders,
                    loaded_at=now()''', (args.source_database, copied))
                dst.execute('ANALYZE mart.canceled_orders')
            target.commit()
        print(f'Published {copied:,} explicitly canceled order IDs from {args.source_database}.', flush=True)
    finally:
        source.close()


if __name__ == '__main__':
    main()
