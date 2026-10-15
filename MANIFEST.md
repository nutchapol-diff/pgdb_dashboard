# Included files

This is a review copy, not a second application repository. Files are copied from `mssql_airflow/prototypes/radops_star` and kept in the same functional groups used by the prototype.

| Directory | Contents |
|---|---|
| `sqlserver/` | SQL Server source extract statements |
| `postgres/schema/` | PostgreSQL/TimescaleDB DDL |
| `postgres/load/` | target staging, load, publish, audit, and analysis SQL |
| `postgres/dashboard/` | read-only dashboard and explorer SQL |
| `python/loaders/` | source-to-target loader entrypoints |
| `dashboard/` | Streamlit app, widget modules, requirements, Dockerfile, offline guide |
| `flow/` | Mermaid and plain-language pipeline diagram |

`dashboard/sql/` and `python/loaders/sql/` mirror the top-level SQL folders only to preserve the original relative paths used by the copied entrypoints.

Excluded on purpose: `.env` files, passwords, notebooks, generated PDF/report output, test-only files, Airflow orchestration, archive/CDC jobs, and unrelated BI services.
