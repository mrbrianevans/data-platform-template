"""Identifiers and BigQuery SQL for the ``(id, data)`` ingest path.

Table identifiers are quoted and restricted to a safe character set so the
statements this module builds cannot be rewritten by a malformed name. The
DuckDB ``id`` expression is caller-supplied SQL and is embedded as an
expression, not as a statement.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_COLUMN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TEMP_TABLE_EXPIRY_DAYS = 1


class IngestConfigError(ValueError):
    """Raised when task-group parameters cannot be turned into a safe ingest."""


def quote_ident(name: str) -> str:
    if not isinstance(name, str) or not _IDENT.fullmatch(name):
        raise IngestConfigError(
            f"Invalid BigQuery identifier {name!r}. "
            "Use letters, numbers, underscores and hyphens, starting with a letter or underscore."
        )
    return f"`{name}`"


def _is_template(value: str) -> bool:
    return "{{" in value or "{%" in value


def parse_table_id(table: str, project_id: str | None = None) -> tuple[str, str, str]:
    """Return ``(project, dataset, table)`` from a fully qualified id.

    ``dataset.table`` is accepted when ``project_id`` is set. Templated values
    are rejected here; callers skip this until Airflow has rendered them.
    """
    if not isinstance(table, str) or not table or _is_template(table):
        raise IngestConfigError("destination_table must be a concrete project.dataset.table id")
    parts = table.split(".")
    if len(parts) == 3:
        project, dataset, name = parts
    elif len(parts) == 2:
        if not project_id:
            raise IngestConfigError(
                "destination_table must be project.dataset.table when project_id is omitted"
            )
        project, dataset, name = project_id, parts[0], parts[1]
    else:
        raise IngestConfigError(
            f"destination_table must be project.dataset.table or dataset.table, got {table!r}"
        )
    for part in (project, dataset, name):
        quote_ident(part)
    return project, dataset, name


def qualified_table(table: str, project_id: str | None = None) -> str:
    """Backtick-quoted ``project.dataset.table`` for use in SQL."""
    project, dataset, name = parse_table_id(table, project_id)
    return f"{quote_ident(project)}.{quote_ident(dataset)}.{quote_ident(name)}"


def unquoted_table(table: str, project_id: str | None = None) -> str:
    """``project.dataset.table`` as the BigQuery API expects it."""
    project, dataset, name = parse_table_id(table, project_id)
    return f"{project}.{dataset}.{name}"


def build_id_expression(
    id_expression: str | None,
    id_columns: Sequence[str] | None,
) -> str:
    """DuckDB expression, evaluated against the JSON column ``data``.

    ``id_columns`` reads those keys out of the record and joins them with
    ``|``. With neither argument, the id is a SHA-256 of the record text, which
    is the fallback for files that have no natural key.
    """
    if id_expression and id_columns:
        raise IngestConfigError("Pass only one of id_expression or id_columns")
    if id_columns is not None:
        if isinstance(id_columns, str) or not id_columns:
            raise IngestConfigError("id_columns must be a non-empty list of column names")
        parts: list[str] = []
        for column in id_columns:
            if not isinstance(column, str) or not _COLUMN.fullmatch(column):
                raise IngestConfigError(
                    f"Invalid id column {column!r}. Use a simple name; "
                    "for nested or transformed keys pass id_expression."
                )
            parts.append(f"json_extract_string(data, '$.{column}')")
        if len(parts) == 1:
            return parts[0]
        return " || '|' || ".join(parts)
    if id_expression is not None:
        if not isinstance(id_expression, str) or not id_expression.strip():
            raise IngestConfigError("id_expression must be a non-empty SQL expression")
        if ";" in id_expression:
            raise IngestConfigError("id_expression must be a single DuckDB expression")
        return id_expression.strip()
    return "sha256(cast(data AS VARCHAR))"


def temporary_table_ids(
    *,
    destination_table: str,
    project_id: str | None,
    dag_id: str,
    group_id: str,
    run_id: str,
) -> tuple[str, str]:
    """Stable stage and diff table ids for one Dag run.

    The same run retries the same tables (load truncates, diff is replaced).
    A different run gets a different suffix, so two runs do not share tables.
    """
    project, dataset, table = parse_table_id(destination_table, project_id)
    digest = hashlib.sha256(f"{dag_id}|{group_id}|{run_id}|{table}".encode()).hexdigest()[:12]
    safe_group = re.sub(r"[^A-Za-z0-9_]", "_", group_id)[:40].strip("_") or "ingest"
    stage = f"_ingest_{safe_group}_{digest}_stage"
    diff = f"_ingest_{safe_group}_{digest}_diff"
    quote_ident(stage)
    quote_ident(diff)
    return f"{project}.{dataset}.{stage}", f"{project}.{dataset}.{diff}"


def create_target_sql(destination_sql: str) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {destination_sql} (\n    id STRING NOT NULL,\n    data JSON NOT NULL\n)"
    )


def build_diff_sql(*, diff_sql: str, stage_sql: str, destination_sql: str) -> str:
    """Rows that are new, or whose canonical JSON hash differs from the target.

    ``PARSE_JSON(..., wide_number_mode => 'round')`` accepts integers that do
    not fit in int64. ``TO_JSON_STRING`` canonicalises key order, so a source
    that re-serialises the same record does not look like a change.
    """
    return (
        f"CREATE OR REPLACE TABLE {diff_sql}\n"
        "OPTIONS (\n"
        "    expiration_timestamp = TIMESTAMP_ADD(\n"
        f"        CURRENT_TIMESTAMP(), INTERVAL {TEMP_TABLE_EXPIRY_DAYS} DAY\n"
        "    )\n"
        ")\n"
        "AS\n"
        "WITH incoming AS (\n"
        "    SELECT\n"
        "        id,\n"
        "        PARSE_JSON(data, wide_number_mode => 'round') AS data\n"
        f"    FROM {stage_sql}\n"
        ")\n"
        "SELECT\n"
        "    incoming.id,\n"
        "    incoming.data\n"
        "FROM incoming\n"
        f"LEFT JOIN {destination_sql} AS target\n"
        "    ON incoming.id = target.id\n"
        "WHERE\n"
        "    target.id IS NULL\n"
        "    OR SHA256(TO_JSON_STRING(incoming.data))\n"
        "        != SHA256(TO_JSON_STRING(target.data))\n"
    )


def merge_sql(*, diff_sql: str, destination_sql: str) -> str:
    return (
        f"MERGE {destination_sql} AS target\n"
        f"USING {diff_sql} AS diff\n"
        "    ON target.id = diff.id\n"
        "WHEN MATCHED THEN\n"
        "    UPDATE SET data = diff.data\n"
        "WHEN NOT MATCHED THEN\n"
        "    INSERT (id, data)\n"
        "    VALUES (diff.id, diff.data)\n"
    )


def diff_rows_sql(diff_sql: str) -> str:
    return f"SELECT id, TO_JSON_STRING(data) AS data FROM {diff_sql}"
