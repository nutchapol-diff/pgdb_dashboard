# Pipeline flow and ownership

## End-to-end path

```text
1. SQL Server source
   RIS_CU.dbo tables are read with the SQL in ../sqlserver/.

2. Extract and load
   A loader in ../python/loaders/ runs the source query, pages large results,
   normalizes values, and sends rows to PostgreSQL with COPY or parameterized
   upserts. Source tables are never updated by this package.

3. Target publish
   ../postgres/schema/ creates the target objects. ../postgres/load/ creates
   staging objects, loads dimensions first, publishes fact/supplementary data,
   refreshes rollups, and records audit/count evidence.

4. Serving
   ../postgres/dashboard/ contains the read-only SQL behind dashboard widgets.
   The Streamlit modules in ../dashboard/ call PostgreSQL only.

5. Inspection
   pgAdmin connects to PostgreSQL beside the flow. It is used to inspect tables,
   constraints, indexes, query plans, and row counts; it does not receive data
   from SQL Server and it is not a second ETL destination.
```

## Ownership and review questions

| Layer | Owns | Review focus |
|---|---|---|
| SQL Server extracts | source joins, filters, source-side aggregation | indexes, sargability, source read load, duplicate grain |
| Python loaders | connection handling, batching, type mapping, retries, publish order | idempotency, checkpoint/audit behavior, error handling |
| PostgreSQL schema/load | keys, constraints, staging, upsert/replace, rollups | types, indexes, Timescale partitioning, transaction scope |
| Dashboard SQL | serving grain and metric definitions | explain plans, stable denominators, null/missing-data behavior |
| Streamlit | presentation and filters | no source access, query reuse, safe connection handling |

## Data safety invariants

- SQL Server credentials are local only; `.env` is not part of this package.
- Source extraction is read-only.
- Values are parameterized; identifiers are selected from controlled code paths.
- A failed load must not be presented as a successful dashboard refresh.
- Raw source keys and timestamps are retained where the target model requires lineage.
- pgAdmin credentials and passwords are deployment secrets, not source files.
