#!/usr/bin/env bash
# Reject managed Airflow (Cloud Composer) resources. They incur significant cost.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

matches="$(grep -RInE --include='*.tf' '^[^#]*google_composer_' "$root/terraform" || true)"

if [[ -n "$matches" ]]; then
  echo "Managed Airflow (Cloud Composer) must not be deployed; it incurs significant cost."
  echo "$matches"
  exit 1
fi

echo "No managed Airflow resources in terraform/."
