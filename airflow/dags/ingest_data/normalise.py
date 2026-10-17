"""Normalise staged files to Parquet ``(id, data)`` with DuckDB.

``data`` is one JSON value for the whole source record. NDJSON is read with
``read_ndjson_objects`` so a row is never parsed into columns: a new field in
a later file cannot change the ingest schema. CSV and Parquet rows are wrapped
with ``to_json`` after CSV values have been read as text, so leading zeros and
date-like codes survive.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import duckdb

from ingest_data.sql import IngestConfigError, build_id_expression

logger = logging.getLogger(__name__)

_COMPRESSED_SUFFIXES = {".gz", ".zip", ".bz2", ".xz", ".zst"}
_ENCODING = re.compile(r"[A-Za-z0-9_-]+")

# Kept as text so tests can lock the "do not infer a schema" choice.
NDJSON_READER = "read_ndjson_objects(?)"
JSON_ARRAY_READER = """unnest(from_json(content, '["JSON"]'))"""


class FileFormat(Enum):
    NDJSON = "ndjson"
    JSON_ARRAY = "json_array"
    CSV = "csv"
    PARQUET = "parquet"


@dataclass(frozen=True)
class NormaliseResult:
    row_count: int
    duplicate_count: int


def resolve_format(path: Path, file_format: str | None) -> FileFormat:
    if file_format and file_format != "auto":
        try:
            return FileFormat(file_format)
        except ValueError as exc:
            raise IngestConfigError(
                f"file_format must be auto, ndjson, json_array, csv or parquet, got {file_format!r}"
            ) from exc
    return detect_format(path)


def detect_format(path: Path) -> FileFormat:
    """Pick a format from the suffix, then from the first bytes."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.endswith((".ndjson", ".jsonl")):
        return FileFormat.NDJSON
    if suffix == ".csv":
        return FileFormat.CSV
    if suffix in {".parquet", ".pq"}:
        return FileFormat.PARQUET
    return _sniff(path)


def _sniff(path: Path) -> FileFormat:
    with path.open("rb") as handle:
        chunk = handle.read(4096)
    if chunk.startswith(b"PAR1"):
        return FileFormat.PARQUET
    stripped = chunk.lstrip()
    if not stripped:
        raise IngestConfigError(f"Cannot detect the format of empty file {path.name}")
    if stripped.startswith(b"["):
        return FileFormat.JSON_ARRAY
    if stripped.startswith(b"{"):
        return FileFormat.NDJSON
    return FileFormat.CSV


def _reject_compressed(path: Path, source_name: str) -> None:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    if suffixes & _COMPRESSED_SUFFIXES:
        raise IngestConfigError(
            f"{source_name} is compressed. Unzip it before ingest_data; the task group reads the "
            "staged JSON, CSV or Parquet only."
        )


def _csv_scan_sql(*, csv_header: bool, csv_encoding: str | None) -> str:
    encoding_sql = ""
    if csv_encoding:
        if not _ENCODING.fullmatch(csv_encoding):
            raise IngestConfigError(f"Invalid csv_encoding {csv_encoding!r}")
        encoding_sql = f", encoding='{csv_encoding}'"
    header = "true" if csv_header else "false"
    # nullstr limits NULL markers to \N so an empty CSV field stays "".
    # all_varchar stops dates and numeric-looking codes being retyped.
    return (
        "SELECT to_json(src) AS data\n"
        "FROM read_csv(\n"
        "    ?,\n"
        f"    header={header},\n"
        "    all_varchar=true,\n"
        "    nullstr='\\N',\n"
        "    delim=?\n"
        f"    {encoding_sql}\n"
        ") AS src"
    )


def scan_sql(
    fmt: FileFormat,
    *,
    csv_header: bool = True,
    csv_encoding: str | None = None,
) -> tuple[str, int]:
    """Return ``(SELECT data ... SQL, number of path/option parameters)``.

    The SQL yields one column, ``data``, of JSON values. Parameters are bound
    left to right and always start with the file path.
    """
    if fmt is FileFormat.NDJSON:
        return f"SELECT json AS data FROM {NDJSON_READER}", 1
    if fmt is FileFormat.JSON_ARRAY:
        select_sql = (
            "SELECT record AS data FROM (\n"
            f"    SELECT {JSON_ARRAY_READER} AS record\n"
            "    FROM read_text(?)\n"
            ")"
        )
        return select_sql, 1
    if fmt is FileFormat.CSV:
        return _csv_scan_sql(csv_header=csv_header, csv_encoding=csv_encoding), 2
    if fmt is FileFormat.PARQUET:
        return "SELECT to_json(src) AS data FROM read_parquet(?) AS src", 1
    raise IngestConfigError(f"Unsupported format {fmt!r}")


def _json_array_kind(connection: duckdb.DuckDBPyConnection, path: Path) -> str:
    row = connection.execute(
        """
        SELECT
            CASE
                WHEN content IS NULL OR length(trim(content)) = 0 THEN 'EMPTY'
                ELSE json_type(content::JSON)
            END
        FROM read_text(?)
        """,
        [str(path)],
    ).fetchone()
    if row is None or row[0] is None:
        return "EMPTY"
    return str(row[0])


def _load_file(
    connection: duckdb.DuckDBPyConnection,
    *,
    fmt: FileFormat,
    source_name: str,
    path: Path,
    source_ord: int,
    csv_delimiter: str,
    csv_header: bool,
    csv_encoding: str | None,
) -> None:
    if fmt is FileFormat.JSON_ARRAY:
        try:
            kind = _json_array_kind(connection, path)
        except duckdb.Error as exc:
            raise IngestConfigError(f"Failed to read {source_name} as a JSON array: {exc}") from exc
        if kind == "EMPTY":
            logger.warning("Source file %s is empty; no records read", source_name)
            return
        if kind != "ARRAY":
            raise IngestConfigError(
                f"{source_name} is a JSON {kind}, not a top-level array. "
                "Stage a JSON array, or use NDJSON (file_format='ndjson')."
            )
    select_sql, param_count = scan_sql(fmt, csv_header=csv_header, csv_encoding=csv_encoding)
    # Placeholders are bound left to right. The two outer ones (source name and
    # ordinal) appear before the path placeholder inside the scan.
    params: list[object] = [source_name, source_ord, str(path)]
    if param_count == 2:
        params.append(csv_delimiter)
    statement = f"INSERT INTO raw_records\nSELECT data, ?, ?, row_number() OVER ()\nFROM ({select_sql})"
    try:
        connection.execute(statement, params)
    except duckdb.Error as exc:
        raise IngestConfigError(f"Failed to read {source_name} as {fmt.value}: {exc}") from exc


def normalise_files(
    files: list[tuple[str, Path]],
    output_path: Path,
    *,
    file_format: str | None = "auto",
    id_expression: str | None = None,
    id_columns: list[str] | tuple[str, ...] | None = None,
    csv_delimiter: str = ",",
    csv_header: bool = True,
    csv_encoding: str | None = None,
) -> NormaliseResult:
    """Write a Parquet file of ``(id, data)`` and return how many rows survived.

    ``files`` is ``(display name, local path)`` in precedence order. When the
    same id appears more than once, the last row is kept.
    """
    if not files:
        raise IngestConfigError("No source files to normalise")
    if csv_delimiter == "" or any(char in csv_delimiter for char in "\r\n"):
        raise IngestConfigError("csv_delimiter must not be empty or contain a newline")
    id_expr = build_id_expression(id_expression, id_columns)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect()
    try:
        temp_dir = str(output_path.parent).replace("'", "''")
        connection.execute(f"SET temp_directory = '{temp_dir}'")
        try:
            connection.execute(
                "SELECT (" + id_expr + ") AS id FROM (SELECT CAST(NULL AS JSON) AS data) WHERE FALSE"
            )
        except duckdb.Error as exc:
            raise IngestConfigError(f"id expression is not valid DuckDB SQL: {exc}") from exc

        connection.execute(
            """
            CREATE TABLE raw_records (
                data JSON,
                source_file VARCHAR,
                source_ord BIGINT,
                source_row BIGINT
            )
            """
        )
        for ordinal, (source_name, path) in enumerate(files):
            _reject_compressed(path, source_name)
            fmt = resolve_format(path, file_format)
            logger.info("Reading %s as %s", source_name, fmt.value)
            _load_file(
                connection,
                fmt=fmt,
                source_name=source_name,
                path=path,
                source_ord=ordinal,
                csv_delimiter=csv_delimiter,
                csv_header=csv_header,
                csv_encoding=csv_encoding,
            )

        connection.execute(
            "CREATE TABLE keyed AS\n"
            "SELECT\n"
            "    (" + id_expr + ") AS id,\n"
            "    cast(data AS VARCHAR) AS data,\n"
            "    source_file,\n"
            "    source_ord,\n"
            "    source_row\n"
            "FROM raw_records"
        )
        missing = connection.execute(
            """
            SELECT source_file, count(*)
            FROM keyed
            WHERE id IS NULL OR length(trim(cast(id AS VARCHAR))) = 0
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
        if missing:
            detail = ", ".join(f"{name} ({count} rows)" for name, count in missing[:5])
            raise IngestConfigError(
                "id expression produced an empty id. "
                "Check id_columns or id_expression against the staged records. "
                f"Affected files: {detail}"
            )

        counts = connection.execute("SELECT count(*), count(DISTINCT id) FROM keyed").fetchone()
        if counts is None:
            raise IngestConfigError("DuckDB returned no row when counting ids")
        input_rows, distinct_ids = counts
        duplicate_count = int(input_rows) - int(distinct_ids)
        if duplicate_count:
            logger.warning(
                "Dropped %s duplicate ids; the last staged row for each id was kept",
                duplicate_count,
            )
        connection.execute(
            """
            COPY (
                SELECT id, data
                FROM (
                    SELECT
                        id,
                        data,
                        row_number() OVER (
                            PARTITION BY id
                            ORDER BY source_ord DESC, source_row DESC
                        ) AS rn
                    FROM keyed
                )
                WHERE rn = 1
                ORDER BY id
            ) TO ? (FORMAT PARQUET)
            """,
            [str(output_path)],
        )
    finally:
        connection.close()

    counted = duckdb.connect()
    try:
        counted_row = counted.execute(
            "SELECT count(*) FROM read_parquet(?)",
            [str(output_path)],
        ).fetchone()
        if counted_row is None:
            raise IngestConfigError(f"DuckDB could not read {output_path}")
        row_count = counted_row[0]
    finally:
        counted.close()
    return NormaliseResult(row_count=int(row_count), duplicate_count=duplicate_count)
