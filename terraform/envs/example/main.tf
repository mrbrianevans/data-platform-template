terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.7"
    }
  }

  # Configure a remote backend per env, e.g.:
  # backend "gcs" {
  #   bucket = "<name>-tfstate"
  #   prefix = "data-platform"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Wire modules here as they are implemented, e.g.:
# module "bigquery" {
#   source     = "../../modules/bigquery"
#   project_id = var.project_id
#   location   = var.region
# }
#
# The demo project is terraform/envs/demo, applied by .github/workflows/deploy.yml.
# Do not wire terraform/modules/airflow. Managed Airflow incurs significant cost.
