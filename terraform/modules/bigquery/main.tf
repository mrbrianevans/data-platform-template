locals {
  datasets = {
    raw          = "Landed source rows as id and data JSON."
    staging      = "Typed staging models (stg_*)."
    intermediate = "Intermediate models (int_*)."
    marts        = "Mart models (fct_* and dim_*)."
    analytics    = "dbt prod target dataset. Layer models use their own datasets."
  }
}

resource "google_bigquery_dataset" "layer" {
  for_each = local.datasets

  project                    = var.project_id
  dataset_id                 = each.key
  location                   = var.location
  description                = each.value
  delete_contents_on_destroy = false

  labels = {
    managed_by = "terraform"
  }
}
