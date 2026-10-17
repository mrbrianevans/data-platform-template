variable "project_id" {
  description = "GCP project ID for this deployment."
  type        = string
}

variable "region" {
  description = "GCP region. Defaults to London."
  type        = string
  default     = "europe-west2"
}
