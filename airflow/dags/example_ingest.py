"""Example of calling ``ingest_data``. This is not a source connector.

It is unscheduled. Triggering it would read ``gs://example-bucket``, which is
not a real bucket in this template. Copy the call into a source Dag once that
Dag has staged its own files.

Other shapes, not wired up here::

    # Charity Commission direct JSON is one array. organisation_number is the id.
    ingest_data(
        group_id="ingest_charities",
        source_uris="gs://bucket/charity/*.json",
        destination_table="project.raw.charity_commission",
        pubsub_topic="projects/project/topics/raw-charity-commission",
        file_format="json_array",
        id_columns=["organisation_number"],
    )

    # Bank holidays have no single key. division and date together identify a row.
    ingest_data(
        group_id="ingest_bank_holidays",
        source_uris="gs://bucket/bank_holidays/*.csv",
        destination_table="project.raw.bank_holidays",
        pubsub_topic="bank-holidays",
        file_format="csv",
        id_columns=["division", "date"],
        project_id="project",
    )

    # The ACSP list has no natural id, so the row hash is the id.
    ingest_data(
        group_id="ingest_acsp",
        source_uris=["gs://bucket/acsp/acsp.csv"],
        destination_table="project.raw.acsp",
        pubsub_topic="projects/project/topics/raw-acsp",
        file_format="csv",
    )
"""

from __future__ import annotations

from datetime import datetime

from airflow.sdk import DAG

from ingest_data import ingest_data

with DAG(
    dag_id="example_ingest",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["example"],
    doc_md=(
        "Example only. A source Dag stages files in GCS, then calls `ingest_data`. See `docs/ingest-data.md`."
    ),
) as dag:
    ingest_data(
        group_id="ingest_items",
        source_uris="gs://example-bucket/raw/items/*.ndjson",
        destination_table="example-project.raw.items",
        pubsub_topic="projects/example-project/topics/raw-items",
        file_format="ndjson",
        id_columns=["id"],
        project_id="example-project",
    )
