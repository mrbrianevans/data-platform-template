# Security

- Secrets live only in Secret Manager. tfvars and code reference them by name. Never commit secret values, service account keys or `.env` files.
- Service accounts are least-privilege and managed in `terraform/modules/iam`.
- All resources default to `europe-west2`.
- CI uses no production credentials: dbt runs `parse` only (offline), Terraform runs `validate` only.
