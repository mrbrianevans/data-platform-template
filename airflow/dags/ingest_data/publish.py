"""Publish one Pub/Sub event per changed row."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from typing import Any

from ingest_data.sql import IngestConfigError

logger = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 9 * 1024 * 1024
MAX_ATTRIBUTE_BYTES = 1024
PUBLISH_BATCH = 200
SCHEMA_VERSION = 1


def topic_path(topic: str, project_id: str | None) -> str:
    """Accept a short topic id or ``projects/<project>/topics/<topic>``."""
    if not isinstance(topic, str) or not topic:
        raise IngestConfigError("pubsub_topic is required")
    if topic.startswith("projects/") and "/topics/" in topic:
        return topic
    if not project_id:
        raise IngestConfigError(
            "project_id is required when pubsub_topic is not projects/<project>/topics/<topic>"
        )
    if "/" in topic:
        raise IngestConfigError(
            f"Invalid pubsub_topic {topic!r}. Pass a topic id or projects/<project>/topics/<topic>."
        )
    return f"projects/{project_id}/topics/{topic}"


def _attribute(value: str) -> str | None:
    if len(value.encode("utf-8")) > MAX_ATTRIBUTE_BYTES:
        return None
    return value


def _payload(row: dict[str, Any], destination_table: str) -> dict[str, Any]:
    record_id = row.get("id")
    if record_id is None or str(record_id) == "":
        raise IngestConfigError("Diff row is missing an id")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": str(record_id),
        "destination_table": destination_table,
        "change_type": "upsert",
    }
    raw_data = row.get("data")
    if raw_data is None:
        return payload
    if isinstance(raw_data, str):
        try:
            payload["data"] = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            raise IngestConfigError(f"Diff data for id {record_id!r} is not valid JSON") from exc
    else:
        payload["data"] = raw_data
    return payload


def _encode(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) <= MAX_MESSAGE_BYTES:
        return body
    reduced = {key: value for key, value in payload.items() if key != "data"}
    reduced["data_omitted"] = True
    body = json.dumps(reduced, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise IngestConfigError(
            f"Pub/Sub message for id {payload.get('id')!r} exceeds {MAX_MESSAGE_BYTES} bytes"
        )
    logger.warning("Omitted data for id %s because the Pub/Sub message would exceed 9MiB", payload.get("id"))
    return body


def publish_rows(
    publisher: Any,
    topic: str,
    rows: Iterable[dict[str, Any]],
    *,
    destination_table: str,
) -> int:
    """Publish each row. Returns the number of messages accepted by the client.

    Delivery is at-least-once: a retry of this step republishes the same diff.
    Consumers should treat ``id`` as an idempotency key.
    """
    futures: list[Any] = []
    count = 0

    def flush() -> None:
        for future in futures:
            future.result()
        futures.clear()

    for row in rows:
        payload = _payload(row, destination_table)
        attributes: dict[str, str] = {}
        id_attribute = _attribute(payload["id"])
        if id_attribute is not None:
            attributes["id"] = id_attribute
        table_attribute = _attribute(destination_table)
        if table_attribute is not None:
            attributes["destination_table"] = table_attribute
        futures.append(publisher.publish(topic, _encode(payload), **attributes))
        count += 1
        if len(futures) >= PUBLISH_BATCH:
            flush()
    flush()
    logger.info("Published %s change events to %s", count, topic)
    return count


def publish_diff(
    publisher: Any,
    bq_client: Any,
    *,
    topic: str,
    project_id: str | None,
    diff_table: str,
    destination_table: str,
    rows: Iterator[dict[str, Any]] | None = None,
) -> int:
    """Publish ``diff_table``. ``rows`` overrides the query, for tests."""
    path = topic_path(topic, project_id)
    if rows is None:
        from ingest_data.bigquery import iter_diff_rows

        rows = iter_diff_rows(bq_client, diff_table)
    return publish_rows(publisher, path, rows, destination_table=destination_table)
