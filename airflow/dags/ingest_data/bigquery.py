"""Load, diff, merge and drop the temporary BigQuery tables."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from google.cloud import bigquery

from ingest_data.sql import (
    TEMP_TABLE_EXPIRY_DAYS,
    build_diff_sql,
    create_target_sql,
    diff_rows_sql,
    merge_sql,
    qualified_table,
)

logger = logging.getLogger(__name__)

STAGE_SCHEMA = [
    bigquery.SchemaField("id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("data", "STRING", mode="NULLABLE"),
]


def load_parquet(client: Any, parquet_uri: str, stage_table: str) -> None:
    """Load the normalised Parquet into ``stage_table``, replacing any previous load.

    ``data`` stays a string here. The diff statement parses it as JSON, which
    avoids depending on a Parquet JSON logical type.
    """
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=STAGE_SCHEMA,
    )
    job = client.load_table_from_uri(parquet_uri, stage_table, job_config=job_config)
    job.result()
    table = client.get_table(stage_table)
    table.expires = datetime.now(UTC) + timedelta(days=TEMP_TABLE_EXPIRY_DAYS)
    client.update_table(table, ["expires"])
    logger.info("Loaded %s into %s", parquet_uri, stage_table)


def create_target_and_diff(
    client: Any,
    *,
    stage_table: str,
    diff_table: str,
    destination_table: str,
    project_id: str | None,
) -> None:
    """Create the raw table if needed, then fill the diff table.

    The diff is only inserts and updates. Rows that disappear from a staged
    file are left in the target; this is not a snapshot replace.
    """
    destination_sql = qualified_table(destination_table, project_id)
    stage_sql = qualified_table(stage_table)
    diff_sql = qualified_table(diff_table)
    _run(client, create_target_sql(destination_sql))
    _run(
        client,
        build_diff_sql(
            diff_sql=diff_sql,
            stage_sql=stage_sql,
            destination_sql=destination_sql,
        ),
    )


def merge_diff(
    client: Any,
    *,
    diff_table: str,
    destination_table: str,
    project_id: str | None,
) -> None:
    _run(
        client,
        merge_sql(
            diff_sql=qualified_table(diff_table),
            destination_sql=qualified_table(destination_table, project_id),
        ),
    )


def iter_diff_rows(
    client: Any,
    diff_table: str,
) -> Iterator[dict[str, str | None]]:
    result = client.query(diff_rows_sql(qualified_table(diff_table))).result()
    for row in result:
        yield {"id": row["id"], "data": row["data"]}


def delete_tables(client: Any, tables: list[str]) -> None:
    errors: list[Exception] = []
    for table in tables:
        try:
            client.delete_table(table, not_found_ok=True)
        except Exception as exc:  # noqa: BLE001 — keep deleting the other tables
            errors.append(exc)
    if errors:
        detail = "; ".join(f"{type(exc).__name__}: {exc}" for exc in errors)
        raise RuntimeError(f"Failed to delete temporary tables: {detail}") from errors[0]


def _run(client: Any, sql: str) -> None:
    client.query(sql).result()
