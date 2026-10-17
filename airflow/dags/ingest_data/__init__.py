"""Shared ingestion task group, importable from any Dag as ``from ingest_data import ingest_data``.

Airflow puts the ``dags/`` folder on ``sys.path``, so this package sits next to the Dags.

Pipeline: files staged in GCS (NDJSON, a JSON array, CSV or Parquet) are
normalised with DuckDB to Parquet ``(id, data)``, loaded into a BigQuery temp
table, diffed and MERGEd into the raw table, then each change is published to
Pub/Sub. Every raw table has the shape ``(id STRING, data JSON)`` so upstream
schema changes never break ingestion; typing happens in dbt staging.

See ``docs/ingest-data.md``.
"""

from ingest_data.task_group import ingest_data

__all__ = ["ingest_data"]
