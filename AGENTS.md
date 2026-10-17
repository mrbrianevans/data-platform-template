# AGENTS.md

Conventions and commands for coding agents working in this repo.

## Layout

- `terraform/modules/*` reusable modules; `terraform/envs/<name>` one env per deployment.
- `airflow/dags` one DAG per source plus `dbt_build`; `airflow/dags/ingest_data` shared package (Airflow puts `dags/` on `sys.path`); dependencies via uv (`airflow/pyproject.toml`).
- `dbt/models/{staging,intermediate,marts}`; `dbt/seeds` lookup tables (sample raw data in `seeds/sample_data/` is opt-in). dbt is v2 (Fusion), see `dbt/README.md`.
- `cloud-run/jobs/<name>/index.ts` Bun + TypeScript jobs; `cloud-run/build.ts` (Bun shell `$`) scans them and builds each as a Docker image using its own embedded Dockerfile. Do not add per-job Dockerfiles.
- `docs/` Markdown documentation.

## Rules

- One source = one connector unit: a DAG (or Cloud Run job), `dbt/models/staging/<source>/`, sources YAML, and `docs/connectors/<source>.md`. Add all four together.
- Every source lands in a raw table as `(id, data JSON)` via `ingest_data`. Never add typed columns at ingestion; type in staging.
- Staging models are named `stg_<source>__<entity>`; intermediate `int_*`; marts `fct_*` / `dim_*`.
- dbt is SQL only. No Python models. Models must build on BigQuery and DuckDB (the `ci` target): use `dbt.type_*()` macros and `json_string()` instead of adapter-specific SQL.
- **When adding or changing dbt models, sources, tests, seeds or macros you MUST follow both the [Fivetran dbt SQL guidelines](https://github.com/fivetran/dbt_style_guide/blob/main/sql_guidelines.md) and the [dbt Labs best practices (v2)](https://docs.getdbt.com/best-practices?version=2).** Our summary, resolution of conflicts between them, and a new-model checklist are in `docs/dbt-style-guide.md`; read it first. Key points: lowercase SQL, 4-space indent, trailing commas, 80-char lines, CTEs not subqueries, `ref`/`source` in import CTEs at the top, explicit `as` aliases and join types, `join ... on`, `stg_<source>__<entities>` / `int_<entity>_<verb>` / `fct_*` / `dim_*` naming, every model described with a tested (`unique`, `not_null`) `<entity>_id` primary key, staging is the only layer using `source()` and does no joins.
- SQL Server sources use Datastream (Terraform), never Airflow DAGs.
- Secrets live only in Secret Manager. Reference them by name in tfvars; never commit values, keys or `.env` files.
- Region is `europe-west2` (London) unless an env overrides it.
- Cloud Run jobs only where parallelism is needed. Use Bun and TypeScript.
- Never deploy managed Airflow (Cloud Composer or any other hosted Airflow service). It incurs significant cost. Do not add `google_composer_*` resources, do not apply `terraform/modules/airflow`, and keep that module's `enabled` variable `false`. `scripts/no-managed-airflow.sh` enforces this. BigQuery datasets and tables may be created. Airflow may be run locally with its SQLite metadata database; that is not part of deployment. See `docs/deployment.md`.
- Terraform providers are pinned to the latest major in `versions.tf` and locked in `terraform/envs/*/.terraform.lock.hcl`.
- No Airflow DAG tests and no local docker-compose for Airflow.
- Format Python with `uv run ruff format` from the `airflow/` directory (line length 110 to match Airflow). Run `uv run ruff format --check` before committing. Ruff linting includes Airflow's `AIR` ruleset.

## Commands

```bash
# Terraform
terraform fmt -recursive terraform
terraform -chdir=terraform/envs/example init -backend=false && terraform -chdir=terraform/envs/example validate

# dbt v2 (from dbt/)
dbt format --profiles-dir .   # fix layout; use --check to verify
dbt lint --profiles-dir .
dbt check --profiles-dir .    # project rules in dbt/checks/
dbt parse --profiles-dir .
dbt build --profiles-dir .   # BigQuery: needs credentials and GCP_PROJECT_ID
dbt build --profiles-dir . -t ci --vars '{load_sample_data: true}'   # DuckDB, no credentials

# Airflow (from airflow/, uv-managed)
uv sync
uv add <package>
uv run ruff check .
uv run ruff format --check  # formatting; run `uv run ruff format` to apply

# Cloud Run jobs (from cloud-run/)
bun install
bun run build                # all jobs; bun run build.ts <name> for one
```

## CI

`.github/workflows/`: terraform fmt/validate (and `scripts/no-managed-airflow.sh`), dbt format --check / lint / check / parse / build on DuckDB seeds, Airflow ruff lint, Cloud Run typecheck and image builds. Keep these green.

`deploy.yml` runs on push to `master` (and `workflow_dispatch`). It authenticates to `data-platform-demo-511920` with Workload Identity Federation and applies `terraform/envs/demo` (BigQuery datasets) then `dbt build --target prod`. It must not deploy managed Airflow. Pull requests do not deploy.

## Cursor Cloud specific instructions

- `dbt` (Fusion), `terraform`, `uv`, `bun`, and `bunx` are on `/usr/local/bin`. Non-interactive shells do not load `~/.bashrc`.
- From `dbt/`, verify without GCP: `GCP_PROJECT_ID=ci-placeholder dbt build --profiles-dir . -t ci --vars '{load_sample_data: true}'`. Sample rows land in `dbt/target/ci.duckdb` as `raw.raw_example__items`. BigQuery `dev` and `prod` need `GCP_PROJECT_ID` and application-default credentials, which are not configured here. Do not run `terraform apply` or `dbt build --target prod` from this VM. Continuous deployment is `.github/workflows/deploy.yml`.
- Docker starts on boot for `bun run build` (fuse-overlayfs; this VM has no systemd). There is no Airflow webserver. From `airflow/`, run `uv run ruff check .` and `uv run ruff format --check`. Import DAG packages with `PYTHONPATH=dags`.
- `cloud-run/jobs` can be empty. `bunx tsc` typechecks `build.ts`. `bun run build` exits 0 when no `jobs/<name>/index.ts` exists.
- Terraform providers for `terraform/modules/*` and `terraform/envs/*` are already initialized. Login shells set `TF_PLUGIN_CACHE_DIR=/opt/terraform-plugin-cache`.
