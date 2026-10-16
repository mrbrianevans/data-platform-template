# Connectors

One page per source, `connectors/<source>.md`, covering: connector type (DAG / Cloud Run job / Datastream), required secrets (by name), entities landed, and staging models.

A connector unit consists of:

- an Airflow DAG (or Cloud Run job),
- `dbt/models/staging/<source>/` with sources YAML,
- this docs page.
