# Staging

One folder per source system: `staging/<source>/` containing:

- `_<source>__sources.yml`
- `_<source>__models.yml`
- `stg_<source>__<entities>.sql` (plural entity, double underscore after the source)
- optional `base/base_<source>__<entities>.sql` when joins or unions are needed before staging

Raw tables are `(id, data JSON)`; staging extracts, renames and types the fields. One staging model per raw table, no joins or aggregations, materialized as views. Staging is the only layer that uses `source()`.

See [`docs/dbt-style-guide.md`](../../../docs/dbt-style-guide.md).
