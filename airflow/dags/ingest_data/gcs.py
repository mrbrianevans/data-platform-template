"""Match, download and upload GCS objects. Callers pass a storage client."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from pathlib import Path

from ingest_data.sql import IngestConfigError

_GLOB_CHARS = ("*", "?", "[")


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise IngestConfigError(f"Expected a gs:// URI, got {uri!r}")
    bucket, separator, key = uri[5:].partition("/")
    if not bucket or not separator or not key:
        raise IngestConfigError(f"GCS URI must include a bucket and an object path: {uri!r}")
    if ".." in Path(key).parts:
        raise IngestConfigError(f"GCS URI must not contain '..': {uri!r}")
    return bucket, key


def coerce_uris(source_uris: str | Sequence[str]) -> list[str]:
    if isinstance(source_uris, str):
        uris = [source_uris]
    else:
        try:
            uris = list(source_uris)
        except TypeError as exc:
            raise IngestConfigError("source_uris must be a gs:// URI or a list of them") from exc
    if not uris or any(not isinstance(uri, str) for uri in uris):
        raise IngestConfigError("source_uris must contain at least one gs:// URI or glob")
    return uris


def _is_template(uri: str) -> bool:
    return "{{" in uri or "{%" in uri


def validate_source_uris(source_uris: str | Sequence[str]) -> list[str]:
    """Reject malformed URIs at parse time. Leave Jinja strings for runtime."""
    uris = coerce_uris(source_uris)
    for uri in uris:
        if _is_template(uri):
            continue
        parse_gcs_uri(uri)
    return uris


def _prefix_and_pattern(key: str) -> tuple[str, str, bool]:
    """Return ``(list prefix, fnmatch pattern, is_glob)`` for an object key.

    A key that ends in ``/`` means every object under that prefix. ``*``, ``?``
    and ``[`` are globs. Anything else is one object.
    """
    if key.endswith("/"):
        return key, f"{key}*", True
    indexes = [key.find(char) for char in _GLOB_CHARS if char in key]
    if not indexes:
        return key, key, False
    return key[: min(indexes)], key, True


def list_source_objects(
    client,
    source_uris: str | Sequence[str],
) -> list[tuple[str, str]]:
    """Resolve URIs and globs to ``(bucket, object name)`` pairs.

    Order is the order of ``source_uris``. Within one glob, objects are ordered
    by name. The same object is returned once, at its first match. Later rows
    win when two files contain the same id, so this order is the precedence.
    """
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for uri in coerce_uris(source_uris):
        bucket, key = parse_gcs_uri(uri)
        prefix, pattern, is_glob = _prefix_and_pattern(key)
        if not is_glob:
            item = (bucket, key)
            if item not in seen:
                seen.add(item)
                found.append(item)
            continue
        matches: list[tuple[str, str]] = []
        for blob in client.list_blobs(bucket, prefix=prefix):
            name = getattr(blob, "name", "")
            if not name or name.endswith("/"):
                continue
            if fnmatch.fnmatch(name, pattern):
                matches.append((bucket, name))
        for item in sorted(matches, key=lambda pair: pair[1]):
            if item not in seen:
                seen.add(item)
                found.append(item)
    if not found:
        raise FileNotFoundError(f"No GCS objects matched {list(coerce_uris(source_uris))}")
    return found


def download_objects(
    client,
    objects: list[tuple[str, str]],
    dest_dir: Path,
) -> list[tuple[str, Path]]:
    """Download objects. The local suffix is kept so format detection still works."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, Path]] = []
    for index, (bucket, name) in enumerate(objects):
        local = dest_dir / f"{index:05d}{Path(name).suffix}"
        client.bucket(bucket).blob(name).download_to_filename(str(local))
        files.append((f"gs://{bucket}/{name}", local))
    return files


def upload_file(client, local_path: Path, uri: str) -> None:
    bucket, name = parse_gcs_uri(uri)
    if name.endswith("/"):
        raise IngestConfigError(f"staging URI must be an object path, got {uri!r}")
    client.bucket(bucket).blob(name).upload_from_filename(str(local_path))


def delete_uri(client, uri: str) -> None:
    bucket, name = parse_gcs_uri(uri)
    blob = client.bucket(bucket).blob(name)
    try:
        blob.delete()
    except Exception as exc:
        status = getattr(exc, "code", None)
        if status == 404 or exc.__class__.__name__ in {"NotFound", "FileNotFoundError"}:
            return
        raise


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value).strip("._")
    return cleaned[:80] or "ingest"


def staging_object_uri(
    source_uris: list[str],
    staging_prefix: str | None,
    *,
    dag_id: str,
    run_id: str,
    group_id: str,
) -> str:
    """Parquet object the load task reads.

    ``staging_prefix`` may be a full object path or a prefix ending in ``/``.
    Otherwise the object is written under ``_ingest/`` in the first source bucket.
    """
    if staging_prefix:
        if _is_template(staging_prefix):
            raise IngestConfigError("staging_prefix still contains an unrendered template")
        uri = f"{staging_prefix}normalised.parquet" if staging_prefix.endswith("/") else staging_prefix
        parse_gcs_uri(uri)
        return uri
    bucket, _key = parse_gcs_uri(source_uris[0])
    return (
        f"gs://{bucket}/_ingest/{_safe_path_part(dag_id)}/"
        f"{_safe_path_part(run_id)}/{_safe_path_part(group_id)}/normalised.parquet"
    )
