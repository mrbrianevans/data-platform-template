# AGENTS.md

Conventions and commands for coding agents working in this repo.

## Layout

- `terraform/modules/*` reusable modules; `terraform/envs/<firm>` one env per firm.
- `airflow/dags` one DAG per source plus `dbt_build`; `airflow/include/ingest_data` shared task group; `airflow/tests`.
- `dbt/models/{staging,intermediate,marts}`; `dbt/seeds` sample data for CI.
- `cloud-run/jobs/<name>` Bun + TypeScript jobs with a Dockerfile.
- `docs/` Markdown documentation.

## Rules

- One source = one connector unit: a DAG (or Cloud Run job), `dbt/models/staging/<source>/`, sources YAML, and `docs/connectors/<source>.md`. Add all four together.
- Every source lands in a raw table as `(id, data JSON)` via `ingest_data`. Never add typed columns at ingestion; type in staging.
- Staging models are named `stg_<source>__<entity>`; intermediate `int_*`; marts `fct_*` / `dim_*`.
- dbt is SQL only. No Python models.
- SQL Server sources use Datastream (Terraform), never Airflow DAGs.
- Secrets live only in Secret Manager. Reference them by name in tfvars; never commit values, keys or `.env` files.
- Region is `europe-west2` (London) unless a firm env overrides it.
- Cloud Run jobs only where parallelism is needed. Use Bun and TypeScript.

## Commands

```bash
# Terraform
terraform fmt -recursive terraform
terraform -chdir=terraform/envs/example init -backend=false && terraform -chdir=terraform/envs/example validate

# dbt (from dbt/)
DBT_TARGET=ci DBT_PROFILES_DIR=. dbt build

# Airflow (from airflow/)
pip install -r requirements-dev.txt
ruff check .
pytest

# Local Airflow
docker compose -f airflow/docker-compose.yml up

# Cloud Run job (from cloud-run/jobs/<name>/)
bun install && bun run build
```

## CI

`.github/workflows/`: terraform fmt/validate, dbt build on seeds, Airflow lint + DAG import tests, Cloud Run image builds. Keep these green.
