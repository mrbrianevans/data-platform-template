variable "project_id" {
  description = "GCP project ID for this firm."
  type        = string
}

variable "region" {
  description = "GCP region. Defaults to London."
  type        = string
  default     = "europe-west2"
}

variable "enabled_sources" {
  description = "Connector units to enable for this firm (one DAG or Cloud Run job per source)."
  type        = list(string)
  default     = []
}

variable "sql_server_sources" {
  description = "SQL Server sources replicated via Datastream. Secrets are referenced by Secret Manager name only."
  type = map(object({
    host        = string
    port        = optional(number, 1433)
    secret_name = string
  }))
  default = {}
}
