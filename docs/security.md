# Security

- Secrets live only in Secret Manager. tfvars and code reference them by name. Never commit secret values, service account keys or `.env` files.
- Service accounts are least-privilege and managed in `terraform/modules/iam`.
- All resources default to `europe-west2`.
- Pull-request CI uses no cloud credentials: dbt runs against a local DuckDB file with sample seeds, and Terraform runs `fmt` and `validate` only.
- Deployment to the demo project uses Workload Identity Federation (`google-github-actions/auth@v3`) to impersonate `gh-deploy`. No service account keys are stored in GitHub. See [deployment.md](deployment.md).
- Managed Airflow (Cloud Composer or any other hosted Airflow service) is prohibited. It incurs significant cost.
