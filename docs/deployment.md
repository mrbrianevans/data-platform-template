# Deployment

Pushes to `master` that change Terraform, dbt, or `.github/workflows/deploy.yml` deploy the demo project. A run can also be started with `workflow_dispatch`. Pull requests do not deploy.

## Authentication

Deploy jobs use [Workload Identity Federation](https://github.com/google-github-actions/auth) through `google-github-actions/auth@v3`. No service account keys are stored in GitHub.

| Setting | Value |
| --- | --- |
| Project ID | `data-platform-demo-511920` |
| Project number | `644325351184` |
| Workload identity pool | `github` |
| Workload identity provider | `github` |
| Provider resource | `projects/644325351184/locations/global/workloadIdentityPools/github/providers/github` |
| Service account | `gh-deploy@data-platform-demo-511920.iam.gserviceaccount.com` |

The pool's OIDC provider id is `github`. The service account grants `roles/iam.workloadIdentityUser` to:

```text
principalSet://iam.googleapis.com/projects/644325351184/locations/global/workloadIdentityPools/github/attribute.repository/mrbrianevans/data-platform-template
```

That binding is what lets this repository impersonate `gh-deploy`. The workflow requests an OIDC token (`permissions: id-token: write`) and passes `project_id`, `workload_identity_provider`, and `service_account` to the auth action.

Confirm the provider resource name with:

```bash
gcloud iam workload-identity-pools providers describe github \
  --project=644325351184 \
  --location=global \
  --workload-identity-pool=github \
  --format='value(name)'
```

## What gets deployed

1. **Terraform** (`terraform/envs/demo`) creates BigQuery datasets: `raw`, `staging`, `intermediate`, `marts`, and `analytics` in `europe-west2`. State is kept in the GCS bucket `data-platform-demo-511920-tfstate` (prefix `demo`). The workflow creates that bucket when it is missing.
2. **dbt** runs `dbt build --target prod` against BigQuery in `data-platform-demo-511920`. The prod target uses `method: oauth` and reads the external-account file the auth action writes to `GOOGLE_APPLICATION_CREDENTIALS`. Layer models land in `staging`, `intermediate`, and `marts`. Sample seeds stay disabled.

The deploy service account needs permission to create those datasets, run BigQuery jobs, and create or update the state bucket. It can already create service accounts (`roles/iam.serviceAccountAdmin` or equivalent). This pipeline does not create service accounts yet.

## Managed Airflow is prohibited

Never deploy managed Airflow. Cloud Composer and any other hosted Airflow service incur significant cost.

- Do not add `google_composer_*` resources under `terraform/`.
- Do not call `terraform/modules/airflow` from an environment, and keep that module's `enabled` variable `false`.
- Do not add Composer (or another hosted Airflow product) to `.github/workflows/deploy.yml`.

`scripts/no-managed-airflow.sh` runs in pull-request CI and again before `terraform apply`. BigQuery datasets and tables are in scope for deployment.

Airflow itself can still be run on a laptop. The local metadata database is SQLite unless `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` is set. That local process is for development; it is not part of this pipeline, and this repository does not ship Airflow DAG tests or a docker-compose stack for Airflow.
