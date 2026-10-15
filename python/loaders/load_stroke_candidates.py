"""Read full-history stroke mention flags; atomically replace supplementary metadata.

Uses the same connection environment as load.py. Source is read-only. Numeric
PK windows are bounded by the initial maximum; concurrent source changes are not
a consistent snapshot. Existing exam facts and clinical text are not modified.
"""

import argparse
import io
import os
from pathlib import Path

import pyodbc
import psycopg2

ROOT = Path(__file__).parent / 'sql'
RULE = "RIS_ORDER.CLINICAL_INSTRUCTION LIKE '%stroke%'; candidate only"
ORDER_WINDOW = 50000


def sql(path):
    return (ROOT / path).read_text(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-database', default='RIS_CU')
    parser.add_argument('--target-database', default='radops_cu_prototype')
    args = parser.parse_args()
    if not args.source_database.replace('_', '').isalnum():
        raise ValueError('Source database must contain letters, digits and underscores')
    source = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        f"SERVER={os.getenv('SRC_MSSQL_HOST', '10.10.12.97')},1433;"
        f'DATABASE={args.source_database};'
        f"UID={os.environ['SRC_MSSQL_USER']};PWD={os.environ['SRC_MSSQL_PASSWORD']};"
        'Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;',
        timeout=10, autocommit=True,
    )
    source.timeout = 45
    try:
        target = psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'), port=os.getenv('PGPORT', '6543'),
            dbname=args.target_database, user=os.getenv('PGUSER', 'postgres'),
            password=os.environ['PGPASSWORD'], connect_timeout=10,
        )
        try:
            with target:
                src, dst = source.cursor(), target.cursor()
                # Serialize refreshes of this dataset; readers retain previous committed data.
                dst.execute("SELECT pg_advisory_xact_lock(hashtext('radops_stroke_candidates'))")
                dst.execute(sql('postgres/03_stroke_candidates.sql'))
                dst.execute('CREATE TEMP TABLE stroke_stage (LIKE mart.stroke_candidate_orders INCLUDING ALL) ON COMMIT DROP')
                src.execute(sql('sqlserver/stroke_order_bounds.sql'))
                minimum, maximum, source_count = src.fetchone()
                examined = candidates = 0
                if minimum is not None:
                    for lower in range(minimum, maximum + 1, ORDER_WINDOW):
                        upper = min(lower + ORDER_WINDOW - 1, maximum)
                        src.execute(sql('sqlserver/stroke_orders_page.sql'), (lower, upper, lower, upper))
                        examined += src.fetchone()[0]
                        if not src.nextset():
                            raise RuntimeError('Missing stroke page result set')
                        while batch := src.fetchmany(2000):
                            buffer = io.StringIO()
                            for order_id, canceled in batch:
                                flag = r'\N' if canceled is None else 'true' if canceled else 'false'
                                buffer.write(f'{order_id}\t{flag}\n')
                            buffer.seek(0)
                            dst.copy_expert("COPY stroke_stage FROM STDIN WITH (FORMAT text)", buffer)
                            candidates += len(batch)
                        print(f'Examined {examined:,}/{source_count:,} orders; {candidates:,} stroke candidates; key {upper:,}', flush=True)
                if examined != source_count:
                    raise RuntimeError('Source order count changed; previous serving dataset retained')
                dst.execute('SELECT count(*) FROM stroke_stage')
                if dst.fetchone()[0] != candidates:
                    raise RuntimeError('Stroke stage count mismatch')
                dst.execute(sql('postgres/load/replace_stroke_candidates.sql'))
                dst.execute(sql('postgres/load/upsert_stroke_audit.sql'),
                            (args.source_database, RULE, maximum, examined, candidates))
            print(f'Committed {candidates:,} candidate orders from {examined:,} examined orders.', flush=True)
        finally:
            target.close()
    finally:
        source.close()


if __name__ == '__main__':
    main()
