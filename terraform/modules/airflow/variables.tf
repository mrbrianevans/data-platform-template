variable "enabled" {
  description = "Must stay false. Managed Airflow (Cloud Composer or any other hosted Airflow service) incurs significant cost and is not deployed from this repository. Run Airflow locally with SQLite instead."
  type        = bool
  default     = false

  validation {
    condition     = var.enabled == false
    error_message = "Managed Airflow must not be deployed; it incurs significant cost. Run Airflow locally with SQLite instead."
  }
}
