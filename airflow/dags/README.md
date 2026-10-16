# DAGs

- One DAG per source: `<source>.py`, built on `include/ingest_data`.
- `dbt_build.py`: runs the dbt project after ingestion.

Every DAG must import cleanly (`pytest` in `airflow/` checks this).
