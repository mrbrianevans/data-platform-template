output "dataset_ids" {
  description = "BigQuery dataset ids keyed by layer."
  value       = { for name, dataset in google_bigquery_dataset.layer : name => dataset.dataset_id }
}
