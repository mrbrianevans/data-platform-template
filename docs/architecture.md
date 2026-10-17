# Architecture

The platform deploys to a single GCP project (`europe-west2`) provisioned from `terraform/envs/<name>`.

## Data flow

1. **Ingest.** An Airflow DAG (or Cloud Run job for parallel sources) stages JSON, CSV or Parquet in GCS. The shared [`ingest_data`](ingest-data.md) task group loads it through DuckDB to Parquet `(id, data)`, into a BigQuery temp table, diffs and MERGEs into the raw table, then publishes each change to Pub/Sub.
2. **Raw.** Every raw table is `(id, data JSON)`, so upstream schema changes never break ingestion.
3. **SQL Server.** Replicated by Datastream directly into BigQuery (Terraform-managed), not via DAGs.
4. **Transform.** dbt (SQL only) types data in `staging`, composes in `intermediate`, and publishes `fct_*` / `dim_*` in `marts`.

## Components

Modelling rules for dbt are in [dbt-style-guide.md](dbt-style-guide.md).

See `terraform/modules/` for infrastructure building blocks and `airflow/`, `dbt/`, `cloud-run/` for runtime code.
