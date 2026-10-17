"""Download staged objects and write the normalised Parquet back to GCS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest_data.gcs import download_objects, list_source_objects, upload_file
from ingest_data.normalise import normalise_files


def normalise_staged_objects(
    storage_client: Any,
    source_uris: str | list[str] | tuple[str, ...],
    staging_uri: str,
    work_dir: Path,
    **normalise_kwargs: Any,
) -> dict[str, Any]:
    """Resolve globs, normalise locally, upload ``staging_uri``.

    The upload is what the BigQuery load reads, so a retry of the load task
    does not need the worker disk from the normalise task.
    """
    objects = list_source_objects(storage_client, source_uris)
    files = download_objects(storage_client, objects, work_dir / "sources")
    output = work_dir / "normalised.parquet"
    result = normalise_files(files, output, **normalise_kwargs)
    upload_file(storage_client, output, staging_uri)
    return {
        "parquet_uri": staging_uri,
        "row_count": result.row_count,
        "duplicate_count": result.duplicate_count,
        "object_count": len(objects),
    }
