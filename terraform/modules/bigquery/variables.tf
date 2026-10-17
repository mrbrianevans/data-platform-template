variable "project_id" {
  description = "GCP project ID that owns the datasets."
  type        = string
}

variable "location" {
  description = "BigQuery location. Defaults to London."
  type        = string
  default     = "europe-west2"
}
