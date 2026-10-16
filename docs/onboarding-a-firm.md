# Onboarding a firm

1. Copy this repo's layout into a new private repo.
2. Create `terraform/envs/<firm>/` from `terraform/envs/example/`; set `project_id`, region and `enabled_sources`.
3. Create secrets in Secret Manager out-of-band; reference them by name in tfvars.
4. `terraform apply` the env.
5. Enable sources: DAGs under `airflow/dags`, Datastream for SQL Server, Cloud Run jobs where needed.
6. Run initial loads (local Airflow via `airflow/docker-compose.yml` works for one-off loads).
7. Run `dbt build`; adapt the starter marts for the firm.
