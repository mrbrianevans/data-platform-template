# airflow

Placeholder for an Airflow runtime. This module stays free of cloud resources.

## Managed Airflow is prohibited

Cloud Composer and any other hosted Airflow service incur significant cost. Do not provision them from this module, from `terraform/envs/*`, or from GitHub Actions. `scripts/no-managed-airflow.sh` fails CI when a Composer resource is added. `enabled` must stay `false`.

Continuous deployment ([docs/deployment.md](../../../docs/deployment.md)) applies BigQuery and dbt only. It does not call this module.

To try Airflow while developing, run it locally. Airflow uses a SQLite metadata database unless `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` points somewhere else. Local Airflow is not part of the deploy pipeline. This repository does not run Airflow DAG tests or a local docker-compose stack.

## Files

- `main.tf` resources
- `variables.tf` inputs
- `outputs.tf` outputs
