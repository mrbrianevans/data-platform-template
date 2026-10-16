# AGENTS.md

Conventions and commands for coding agents working in this repo.

## Layout

- `terraform/modules/*` reusable modules; `terraform/envs/<name>` one env per deployment.
- `airflow/dags` one DAG per source plus `dbt_build`; `airflow/dags/ingest_data` shared package (Airflow puts `dags/` on `sys.path`); dependencies via uv (`airflow/pyproject.toml`).
- `dbt/models/{staging,intermediate,marts}`; `dbt/seeds` sample data. dbt is v2 (Fusion), see `dbt/README.md`.
- `cloud-run/jobs/<name>/index.ts` Bun + TypeScript jobs; `cloud-run/build.ts` (Bun shell `$`) scans them and builds each as a Docker image using its own embedded Dockerfile. Do not add per-job Dockerfiles.
- `docs/` Markdown documentation.

## Rules

- One source = one connector unit: a DAG (or Cloud Run job), `dbt/models/staging/<source>/`, sources YAML, and `docs/connectors/<source>.md`. Add all four together.
- Every source lands in a raw table as `(id, data JSON)` via `ingest_data`. Never add typed columns at ingestion; type in staging.
- Staging models are named `stg_<source>__<entity>`; intermediate `int_*`; marts `fct_*` / `dim_*`.
- dbt is SQL only. No Python models.
- SQL Server sources use Datastream (Terraform), never Airflow DAGs.
- Secrets live only in Secret Manager. Reference them by name in tfvars; never commit values, keys or `.env` files.
- Region is `europe-west2` (London) unless an env overrides it.
- Cloud Run jobs only where parallelism is needed. Use Bun and TypeScript.
- Terraform providers are pinned to the latest major in `versions.tf` and locked in `terraform/envs/*/.terraform.lock.hcl`.
- No Airflow DAG tests and no local docker-compose for Airflow.

## Commands

```bash
# Terraform
terraform fmt -recursive terraform
terraform -chdir=terraform/envs/example init -backend=false && terraform -chdir=terraform/envs/example validate

# dbt v2 (from dbt/)
dbt parse --profiles-dir .
dbt build --profiles-dir .   # needs BigQuery credentials and GCP_PROJECT_ID

# Airflow (from airflow/, uv-managed)
uv sync
uv add <package>
uv run ruff check .

# Cloud Run jobs (from cloud-run/)
bun install
bun run build                # all jobs; bun run build.ts <name> for one
```

## CI

`.github/workflows/`: terraform fmt/validate, dbt parse, Airflow ruff lint, Cloud Run typecheck and image builds. Keep these green.
