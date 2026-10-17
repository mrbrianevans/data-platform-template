output "bigquery_dataset_ids" {
  description = "Dataset ids created in the demo project."
  value       = module.bigquery.dataset_ids
}
