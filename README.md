# Radiology operations pipeline review package

This directory is a focused copy of the working prototype path:

```text
SQL Server (10.10.12.97 / RIS_CU)
        │ read-only extracts in sqlserver/
        ▼
Python loaders (python/loaders/)
        │ parameterized SQL + batched COPY/upsert
        ▼
PostgreSQL / TimescaleDB (postgres/schema, postgres/load)
        │ dashboard queries in postgres/dashboard/
        ├──────────────► pgAdmin (review/admin client; no data movement)
        ▼
Streamlit dashboard (dashboard/)
```

## What is included

- `sqlserver/`: source-side extraction SQL. These statements read RIS_CU; they do not modify SQL Server.
- `python/loaders/`: Python orchestration that executes extracts, maps rows, and publishes target data.
- `postgres/schema/`: target database, dimensions, fact, and supplementary-table DDL.
- `postgres/load/`: staging, copy/upsert, replace, rollup, audit, and analyze statements used by the loaders.
- `postgres/dashboard/`: read-only queries used by Streamlit widgets and data explorer pages.
- `dashboard/`: Streamlit entrypoint, widget modules, Dockerfile, requirements, and the offline lineage guide.
- `flow/`: Mermaid and plain-language flow map for reviewers.

The `dashboard/sql/` and `python/loaders/sql/` trees are compatibility copies of the categorized SQL. The copied application entrypoints use the original prototype-relative `sql/...` paths, so reviewers can run them without changing loader behavior. The canonical review locations are the top-level `sqlserver/` and `postgres/` directories.

Generated reports, notebooks, tests, Airflow DAGs, archive jobs, credentials, and unrelated deployment services are intentionally excluded.

## Important boundary

pgAdmin is a PostgreSQL administration and inspection client. It is not an ETL stage. The data path is SQL Server → loader → PostgreSQL/TimescaleDB → Streamlit; pgAdmin connects to PostgreSQL beside the dashboard so a database administrator can inspect schemas, plans, indexes, and row counts.

## Review/run order

1. Copy `.env.example` to `.env` and fill credentials locally. Never commit `.env`.
2. Run the schema files in `postgres/schema/` against the target database.
3. Review `python/loaders/` together with the matching files in `sqlserver/` and `postgres/load/`.
4. Run the loader selected for the required dataset. It publishes dimensions before the fact and records audit/count information.
5. Point pgAdmin at the target (`127.0.0.1:6543` from the host, database `radops_cu_prototype`) to inspect the result.
6. Run the Streamlit app from `dashboard/`; it reads PostgreSQL through the dashboard SQL and does not query SQL Server directly.

For the exact dependency order and ownership, open `flow/pipeline_flow.md` or render `flow/pipeline_flow.mmd` in a Mermaid viewer.
