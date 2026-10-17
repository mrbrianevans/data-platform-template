"""Airflow task group that lands staged GCS files in a raw BigQuery table.

The callables below are created inside :func:`ingest_data` so each Dag can
host more than one dataset. They stay free of closed-over clients: hooks are
opened when the task runs, on Cloud Composer, with ``gcp_conn_id``.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from airflow.sdk import get_current_context, task, task_group

from ingest_data.bigquery import create_target_and_diff, delete_tables, load_parquet, merge_diff
from ingest_data.gcs import delete_uri, staging_object_uri, validate_source_uris
from ingest_data.publish import publish_diff
from ingest_data.sql import IngestConfigError, build_id_expression, parse_table_id, temporary_table_ids
from ingest_data.staging import normalise_staged_objects

logger = logging.getLogger(__name__)

FILE_FORMATS = ("auto", "ndjson", "json_array", "csv", "parquet")
DEFAULT_LOCATION = "europe-west2"


def _validate_format(file_format: str) -> str:
    if file_format not in FILE_FORMATS:
        raise IngestConfigError(f"file_format must be one of {', '.join(FILE_FORMATS)}, got {file_format!r}")
    return file_format


def _is_template(value: str) -> bool:
    return "{{" in value or "{%" in value


def _normalise_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_format": config["file_format"],
        "id_expression": config["id_expression"],
        "id_columns": config["id_columns"],
        "csv_delimiter": config["csv_delimiter"],
        "csv_header": config["csv_header"],
        "csv_encoding": config["csv_encoding"],
    }


def _run_parts() -> tuple[str, str]:
    context = get_current_context()
    dag = context.get("dag")
    run_id = context.get("run_id")
    if dag is None or run_id is None:
        raise RuntimeError("ingest_data tasks must run inside an Airflow task")
    return dag.dag_id, str(run_id)


def _table_ids(destination_table: str, config: dict[str, Any]) -> tuple[str, str, str]:
    dag_id, run_id = _run_parts()
    project, dataset, name = parse_table_id(destination_table, config["project_id"])
    destination = f"{project}.{dataset}.{name}"
    stage, diff = temporary_table_ids(
        destination_table=destination,
        project_id=config["project_id"],
        dag_id=dag_id,
        group_id=config["group_id"],
        run_id=run_id,
    )
    return destination, stage, diff


def _storage_client(gcp_conn_id: str) -> Any:
    from airflow.providers.google.cloud.hooks.gcs import GCSHook

    return GCSHook(gcp_conn_id=gcp_conn_id).get_conn()


def _bigquery_client(gcp_conn_id: str, project_id: str | None, location: str) -> Any:
    from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

    hook = BigQueryHook(gcp_conn_id=gcp_conn_id, location=location)
    if project_id:
        return hook.get_client(project_id=project_id, location=location)
    return hook.get_client(location=location)


def _publisher_client(gcp_conn_id: str) -> Any:
    from airflow.providers.google.cloud.hooks.pubsub import PubSubHook

    return PubSubHook(gcp_conn_id=gcp_conn_id).get_conn()


def ingest_data(
    *,
    group_id: str,
    source_uris: str | Sequence[str],
    destination_table: str,
    pubsub_topic: str,
    file_format: str = "auto",
    id_expression: str | None = None,
    id_columns: Sequence[str] | None = None,
    project_id: str | None = None,
    location: str = DEFAULT_LOCATION,
    gcp_conn_id: str = "google_cloud_default",
    staging_prefix: str | None = None,
    csv_delimiter: str = ",",
    csv_header: bool = True,
    csv_encoding: str | None = None,
):
    """Build the normalise, load, diff, merge, publish and cleanup tasks.

    ``source_uris``, ``destination_table`` and ``pubsub_topic`` are templated,
    so a Dag can pass ``gs://bucket/raw/{{ ds }}/*.ndjson``. See
    ``docs/ingest-data.md`` for the parameters and the ``(id, data)`` layout.

    The return value is the task group, which can be chained with ``>>``.
    """
    if not group_id or not isinstance(group_id, str):
        raise IngestConfigError("group_id is required")
    _validate_format(file_format)
    columns = list(id_columns) if id_columns is not None else None
    build_id_expression(id_expression, columns)
    validate_source_uris(source_uris)
    if not isinstance(destination_table, str) or not destination_table:
        raise IngestConfigError("destination_table is required")
    if not _is_template(destination_table):
        parse_table_id(destination_table, project_id)
    if not isinstance(pubsub_topic, str) or not pubsub_topic:
        raise IngestConfigError("pubsub_topic is required")
    if not _is_template(pubsub_topic):
        from ingest_data.publish import topic_path

        topic_path(pubsub_topic, project_id)
    if csv_delimiter == "" or len(csv_delimiter) > 8 or any(char in csv_delimiter for char in "\r\n"):
        raise IngestConfigError("csv_delimiter must be 1-8 characters and must not contain a newline")
    if staging_prefix is not None and not _is_template(staging_prefix):
        staging_object_uri(
            ["gs://staging-check/object"],
            staging_prefix,
            dag_id="dag",
            run_id="run",
            group_id=group_id,
        )

    config: dict[str, Any] = {
        "file_format": file_format,
        "id_expression": id_expression,
        "id_columns": columns,
        "project_id": project_id,
        "location": location,
        "gcp_conn_id": gcp_conn_id,
        "staging_prefix": staging_prefix,
        "csv_delimiter": csv_delimiter,
        "csv_header": csv_header,
        "csv_encoding": csv_encoding,
        "group_id": group_id,
    }

    @task_group(group_id=group_id)
    def _ingest(
        source_uris: str | list[str],
        destination_table: str,
        pubsub_topic: str,
        config: dict[str, Any],
    ) -> None:
        @task
        def normalise(source_uris: str | list[str], config: dict[str, Any]) -> dict[str, Any]:
            """Step 1. DuckDB writes Parquet of ``(id, data)`` and uploads it."""
            uris = validate_source_uris(source_uris)
            dag_id, run_id = _run_parts()
            staging_uri = staging_object_uri(
                uris,
                config["staging_prefix"],
                dag_id=dag_id,
                run_id=run_id,
                group_id=config["group_id"],
            )
            with tempfile.TemporaryDirectory(prefix="ingest_") as work:
                staged = normalise_staged_objects(
                    _storage_client(config["gcp_conn_id"]),
                    uris,
                    staging_uri,
                    work_dir=Path(work),
                    **_normalise_kwargs(config),
                )
            logger.info(
                "Normalised %s objects to %s (%s rows, %s duplicate ids dropped)",
                staged["object_count"],
                staging_uri,
                staged["row_count"],
                staged["duplicate_count"],
            )
            return staged

        @task
        def load_temp_table(
            staged: Any,
            destination_table: str,
            config: dict[str, Any],
        ) -> dict[str, Any]:
            """Step 2. Load the Parquet into a temporary BigQuery table."""
            destination, stage, diff = _table_ids(destination_table, config)
            load_parquet(
                _bigquery_client(config["gcp_conn_id"], config["project_id"], config["location"]),
                staged["parquet_uri"],
                stage,
            )
            return {
                **staged,
                "destination_table": destination,
                "stage_table": stage,
                "diff_table": diff,
            }

        @task
        def build_diff(
            loaded: Any,
            destination_table: str,
            config: dict[str, Any],
        ) -> dict[str, Any]:
            """Step 3a. Create the target if needed and write new or changed rows."""
            destination, stage, diff = _table_ids(destination_table, config)
            create_target_and_diff(
                _bigquery_client(config["gcp_conn_id"], config["project_id"], config["location"]),
                stage_table=stage,
                diff_table=diff,
                destination_table=destination,
                project_id=config["project_id"],
            )
            return {**loaded, "destination_table": destination, "stage_table": stage, "diff_table": diff}

        @task
        def merge_changes(
            diffed: Any,
            destination_table: str,
            config: dict[str, Any],
        ) -> dict[str, Any]:
            """Step 3b. MERGE the diff into the raw table. Retrying this is safe."""
            destination, _stage, diff = _table_ids(destination_table, config)
            merge_diff(
                _bigquery_client(config["gcp_conn_id"], config["project_id"], config["location"]),
                diff_table=diff,
                destination_table=destination,
                project_id=config["project_id"],
            )
            return {**diffed, "destination_table": destination, "diff_table": diff}

        @task
        def publish_changes(
            merged: Any,
            pubsub_topic: str,
            destination_table: str,
            config: dict[str, Any],
        ) -> dict[str, Any]:
            """Step 4. Publish one event per diff row. Does not drop the diff table."""
            destination, _stage, diff = _table_ids(destination_table, config)
            count = publish_diff(
                _publisher_client(config["gcp_conn_id"]),
                _bigquery_client(config["gcp_conn_id"], config["project_id"], config["location"]),
                topic=pubsub_topic,
                project_id=config["project_id"],
                diff_table=diff,
                destination_table=destination,
            )
            return {**merged, "published": count, "destination_table": destination, "diff_table": diff}

        @task
        def cleanup(published: Any, config: dict[str, Any]) -> None:
            """Drop the stage and diff tables and delete the staged Parquet."""
            errors: list[Exception] = []
            try:
                delete_tables(
                    _bigquery_client(config["gcp_conn_id"], config["project_id"], config["location"]),
                    [published["stage_table"], published["diff_table"]],
                )
            except Exception as exc:  # noqa: BLE001 — still delete the staged Parquet
                errors.append(exc)
            try:
                delete_uri(_storage_client(config["gcp_conn_id"]), published["parquet_uri"])
            except Exception as exc:  # noqa: BLE001 — report every cleanup failure together
                errors.append(exc)
            if errors:
                detail = "; ".join(f"{type(exc).__name__}: {exc}" for exc in errors)
                raise RuntimeError(f"Failed to clean up ingest temporaries: {detail}") from errors[0]

        staged = normalise(source_uris, config)
        loaded = load_temp_table(staged, destination_table, config)
        diffed = build_diff(loaded, destination_table, config)
        merged = merge_changes(diffed, destination_table, config)
        published = publish_changes(merged, pubsub_topic, destination_table, config)
        cleanup(published, config)

    uris: str | list[str] = source_uris if isinstance(source_uris, str) else list(source_uris)
    return _ingest(uris, destination_table, pubsub_topic, config)
