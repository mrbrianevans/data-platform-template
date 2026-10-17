terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.7"
    }
  }

  # Bucket is created by .github/workflows/deploy.yml before init.
  # Keep the name aligned with TF_STATE_BUCKET in that workflow.
  backend "gcs" {
    bucket = "data-platform-demo-511920-tfstate"
    prefix = "demo"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery only. Managed Airflow is prohibited; see docs/deployment.md
# and terraform/modules/airflow.
module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  location   = var.region
}
