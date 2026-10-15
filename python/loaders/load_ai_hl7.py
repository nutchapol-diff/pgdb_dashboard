"""Full-history AI/HL7 daily aggregates. Read-only source; atomic target refresh.

No accessions, patient identifiers, report text, JSON messages, or HL7 payloads
leave SQL Server. Uses indexed primary-key pages; copies only aggregates.
"""

import argparse
import io
import os

import psycopg2
from psycopg2 import sql as pgsql
import pyodbc

from load import copy_field, sql


DATASETS = {
    'ai_result_daily': ('RIS_EXAMRESULTAI', 'EXAM_RESULT_AI_ID',
                        'event_day, modality_id, score_bucket',
                        'sum(event_count), sum(score_count), sum(score_sum), '
                        'sum(reviewed_count), sum(agreed_count), sum(disagreed_count)'),
    'ai_finding_daily': ('RIS_EXAMRESULTAIDTL', 'EXAM_RESULT_AI_DTL_ID',
                         'event_day, modality_id, finding_name',
                         'sum(event_count), sum(score_count), sum(score_sum), min(score_min), max(score_max)'),
    'hl7_ie_daily': ('RIS_HL7IELOG', 'LOG_ID',
                     'event_day, sender, receiver, message_type, status_code, ack_code, is_deleted',
                     'sum(event_count)'),
    'hl7_transaction_daily': ('RIS_HL7TRANSACTIONLOG', 'LOG_NO',
                              'event_day, message_type, trans_type, trans_with',
                              'sum(event_count), sum(sent_count), sum(ack_count), sum(valid_delay_count), '
                              'sum(negative_delay_count), sum(delay_ms_sum), sum(delay_le_1s), '
                              'sum(delay_1_5s), sum(delay_5_30s), sum(delay_gt_30s)'),
}


def aggregate_pages(cursor, name, page_size):
    table, key, _, _ = DATASETS[name]  # Only fixed, internal identifiers.
    cursor.execute(sql('sqlserver/integration_bounds.sql').format(table=table, key=key))
    minimum, maximum = cursor.fetchone()
    if minimum is None:
        return
    last = minimum - 1
    statement = sql(f'sqlserver/{name}_extract.sql')
    while True:
        cursor.execute(statement, (page_size, last, maximum))
        columns = [col[0].lower() for col in cursor.description]
        count_index = columns.index('event_count')
        rows = cursor.fetchall()
        if not rows:
            break
        next_key = max(row[-1] for row in rows)
        if next_key <= last:
            raise RuntimeError('Source key did not advance')
        yield [tuple(row[:-1]) for row in rows]
        last = next_key
        if sum(row[count_index] for row in rows) < page_size:
            break


def refresh_dataset(src, dst, name, page_size):
    table, key, dimensions, measures = DATASETS[name]
    src.execute(sql('sqlserver/integration_count.sql').format(table=table))
    expected = src.fetchone()[0]
    identifier = pgsql.Identifier(name)
    dst.execute(pgsql.SQL(sql('postgres/load/integration_stage.sql')).format(table=identifier))
    total = 0
    for rows in aggregate_pages(src, name, page_size):
        data = io.StringIO()
        for row in rows:
            data.write('\t'.join(copy_field(value) for value in row) + '\n')
        data.seek(0)
        dst.copy_expert(sql('postgres/load/copy_integration_stage.sql'), data)
        count_index = 3 if name in ('ai_result_daily', 'ai_finding_daily') else (7 if name == 'hl7_ie_daily' else 4)
        total += sum(row[count_index] for row in rows)
        print(f'{name}: {total:,}/{expected:,} source records', flush=True)
    if total != expected:
        raise RuntimeError(f'{name}: source/extract mismatch {expected} vs {total}')
    dst.execute(pgsql.SQL(sql('postgres/load/clear_integration_mart.sql')).format(table=identifier))
    # Dimensions and measures come from the fixed DATASETS declarations above.
    dst.execute(pgsql.SQL(sql('postgres/load/rollup_integration_stage.sql')).format(
        table=identifier, dimensions=pgsql.SQL(dimensions), measures=pgsql.SQL(measures)))
    dst.execute(pgsql.SQL(sql('postgres/load/count_integration_mart.sql')).format(table=identifier))
    loaded, undated = dst.fetchone()
    if loaded != expected:
        raise RuntimeError(f'{name}: target validation failed')
    dst.execute(sql('postgres/load/drop_integration_stage.sql'))
    dst.execute(pgsql.SQL(sql('postgres/load/analyze_integration_mart.sql')).format(table=identifier))
    return expected, loaded, undated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-database', default='RIS_CU')
    parser.add_argument('--target-database', default='radops_cu_prototype')
    parser.add_argument('--page-size', type=int, default=100_000)
    args = parser.parse_args()
    if not args.source_database.replace('_', '').isalnum() or args.page_size <= 0:
        raise ValueError('Invalid source database or page size')
    host = os.getenv('SRC_MSSQL_HOST', '10.10.12.97')
    source = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        f'SERVER={host},1433;DATABASE={args.source_database};'
        f"UID={os.environ['SRC_MSSQL_USER']};PWD={os.environ['SRC_MSSQL_PASSWORD']};"
        'Encrypt=no;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;',
        timeout=10, autocommit=True)
    source.timeout = 180
    try:
        with psycopg2.connect(host=os.getenv('PGHOST', '127.0.0.1'), port=os.getenv('PGPORT', '6543'),
                              dbname=args.target_database, user=os.getenv('PGUSER', 'postgres'),
                              password=os.environ['PGPASSWORD']) as target:
            with source.cursor() as src, target.cursor() as dst:
                dst.execute(sql('postgres/load/integration_source_identity.sql'))
                identity = dst.fetchone()
                if identity is None or identity[0] != args.source_database:
                    raise ValueError('Target must contain an exam star loaded from the same source database')
                dst.execute(sql('postgres/02_ai_hl7.sql'))
                for name in DATASETS:
                    expected, loaded, undated = refresh_dataset(src, dst, name, args.page_size)
                    dst.execute(sql('postgres/load/upsert_integration_audit.sql'),
                        (name, host, args.source_database, expected, loaded, undated,
                         'Read committed, fixed maximum key per table; counts verified. '
                         'Source snapshot isolation disabled: concurrent updates are not a point-in-time snapshot.'))
        print('AI and HL7 aggregates committed; all source/target counts match.', flush=True)
    finally:
        source.close()


if __name__ == '__main__':
    main()
