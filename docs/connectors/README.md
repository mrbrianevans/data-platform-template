# Connectors

One page per source, `connectors/<source>.md`, covering: connector type (DAG / Cloud Run job / Datastream), required secrets (by name), entities landed, and staging models.

A connector unit consists of:

- an Airflow DAG (or Cloud Run job),
- `dbt/models/staging/<source>/` with `_<source>__sources.yml`, `_<source>__models.yml` and `stg_<source>__<entities>.sql` (see [dbt style guide](../dbt-style-guide.md)),
- this docs page.
