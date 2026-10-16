"""Shared ingestion task group.

Pipeline: GCS NDJSON -> DuckDB -> Parquet -> BigQuery temp table -> diff/MERGE
into the raw table. Every raw table has the shape ``(id STRING, data JSON)`` so
upstream schema changes never break ingestion; typing happens in dbt staging.
"""
