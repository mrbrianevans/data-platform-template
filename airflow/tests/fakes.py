"""In-memory stand-ins for the GCS and BigQuery clients."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class FakeBlob:
    def __init__(self, name: str, data: bytes = b"") -> None:
        self.name = name
        self.data = data
        self.deleted = False

    def download_to_filename(self, filename: str) -> None:
        if self.deleted:
            raise FileNotFoundError(self.name)
        Path(filename).write_bytes(self.data)

    def upload_from_filename(self, filename: str) -> None:
        self.data = Path(filename).read_bytes()
        self.deleted = False

    def delete(self) -> None:
        if self.deleted:
            raise FileNotFoundError(self.name)
        self.deleted = True


class FakeBucket:
    def __init__(self) -> None:
        self.blobs: dict[str, FakeBlob] = {}

    def blob(self, name: str) -> FakeBlob:
        return self.blobs.setdefault(name, FakeBlob(name))


class FakeStorage:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket())

    def list_blobs(self, bucket: str, prefix: str = ""):
        return [
            blob
            for blob in self.bucket(bucket).blobs.values()
            if blob.name.startswith(prefix) and not blob.deleted
        ]

    def add(self, uri: str, data: bytes) -> FakeBlob:
        from ingest_data.gcs import parse_gcs_uri

        bucket, name = parse_gcs_uri(uri)
        blob = FakeBlob(name, data)
        self.bucket(bucket).blobs[name] = blob
        return blob


class FakeQuery:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []

    def result(self) -> list[dict]:
        return self._rows


class FakeBigQuery:
    def __init__(self, diff_rows: list[dict] | None = None) -> None:
        self.queries: list[str] = []
        self.loads: list[dict] = []
        self.deleted: list[str] = []
        self.updated: list[str] = []
        self.diff_rows = diff_rows or []
        self.fail_deletes: set[str] = set()

    def query(self, sql: str) -> FakeQuery:
        self.queries.append(sql)
        if sql.strip().upper().startswith("SELECT ID"):
            return FakeQuery(self.diff_rows)
        return FakeQuery([])

    def load_table_from_uri(self, uri: str, table: str, job_config) -> FakeQuery:
        self.loads.append(
            {
                "uri": uri,
                "table": table,
                "source_format": job_config.source_format,
                "write_disposition": job_config.write_disposition,
                "schema": [(field.name, field.field_type, field.mode) for field in job_config.schema],
            }
        )
        return FakeQuery([])

    def get_table(self, table: str) -> SimpleNamespace:
        return SimpleNamespace(expires=None, table_id=table)

    def update_table(self, table, fields: list[str]) -> None:
        self.updated.append(fields[0] if fields else "")
        if table.expires is None:
            raise AssertionError("stage table expiry was not set")

    def delete_table(self, table: str, not_found_ok: bool = False) -> None:
        if table in self.fail_deletes:
            raise RuntimeError(f"cannot delete {table}")
        self.deleted.append(table)


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def publish(self, topic: str, data: bytes, **attributes: str):
        self.messages.append({"topic": topic, "data": data, "attributes": attributes})
        return SimpleNamespace(result=lambda: "message-id")
