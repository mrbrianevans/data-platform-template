"""GCS matching and Pub/Sub publishing with the clients mocked."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import bootstrap
import duckdb
from fakes import FakePublisher, FakeStorage

from ingest_data.gcs import delete_uri, list_source_objects, staging_object_uri
from ingest_data.publish import publish_rows, topic_path
from ingest_data.sql import IngestConfigError
from ingest_data.staging import normalise_staged_objects

FIXTURES = bootstrap.FIXTURES


class GcsMatchingTest(unittest.TestCase):
    def test_globs_filter_and_a_trailing_slash_lists_the_prefix(self) -> None:
        storage = FakeStorage()
        storage.add("gs://bucket/raw/2024-01.ndjson", b"{}\n")
        storage.add("gs://bucket/raw/2024-02.ndjson", b"{}\n")
        storage.add("gs://bucket/raw/notes.txt", b"ignore")
        storage.add("gs://bucket/other/2024-03.ndjson", b"{}\n")

        matched = list_source_objects(storage, "gs://bucket/raw/*.ndjson")
        self.assertEqual(
            matched,
            [
                ("bucket", "raw/2024-01.ndjson"),
                ("bucket", "raw/2024-02.ndjson"),
            ],
        )
        under_prefix = list_source_objects(storage, "gs://bucket/raw/")
        self.assertEqual(
            [name for _bucket, name in under_prefix],
            ["raw/2024-01.ndjson", "raw/2024-02.ndjson", "raw/notes.txt"],
        )

    def test_exact_uri_does_not_need_a_listing_and_a_miss_raises(self) -> None:
        storage = FakeStorage()
        storage.add("gs://bucket/one.csv", b"a\n")
        self.assertEqual(
            list_source_objects(storage, ["gs://bucket/one.csv", "gs://bucket/one.csv"]),
            [("bucket", "one.csv")],
        )
        with self.assertRaises(FileNotFoundError):
            list_source_objects(storage, "gs://bucket/missing/*.csv")

    def test_delete_uri_ignores_a_missing_object(self) -> None:
        storage = FakeStorage()
        blob = storage.add("gs://bucket/staged/file.parquet", b"parquet")
        delete_uri(storage, "gs://bucket/staged/file.parquet")
        self.assertTrue(blob.deleted)
        delete_uri(storage, "gs://bucket/staged/file.parquet")

    def test_staging_uri_defaults_and_accepts_a_prefix(self) -> None:
        self.assertEqual(
            staging_object_uri(
                ["gs://bucket/raw/file.ndjson"],
                None,
                dag_id="companies_house",
                run_id="manual__2024-01-01T00:00:00+00:00",
                group_id="ingest",
            ),
            "gs://bucket/_ingest/companies_house/manual__2024-01-01T00_00_00_00_00/ingest/normalised.parquet",
        )
        self.assertEqual(
            staging_object_uri(
                ["gs://bucket/raw/file.ndjson"],
                "gs://stage/prefix/",
                dag_id="dag",
                run_id="run",
                group_id="group",
            ),
            "gs://stage/prefix/normalised.parquet",
        )

    def test_fake_gcs_round_trip_normalises_sample_ndjson(self) -> None:
        storage = FakeStorage()
        storage.add(
            "gs://bucket/raw/companies_house.ndjson",
            (FIXTURES / "companies_house.ndjson").read_bytes(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            staged = normalise_staged_objects(
                storage,
                "gs://bucket/raw/*.ndjson",
                "gs://bucket/_ingest/run/normalised.parquet",
                Path(tmp),
                file_format="ndjson",
                id_columns=["resource_uri"],
            )
            blob = storage.bucket("bucket").blobs["_ingest/run/normalised.parquet"]
            self.assertFalse(blob.deleted)
            self.assertGreater(len(blob.data), 0)
            local = Path(tmp) / "downloaded.parquet"
            local.write_bytes(blob.data)
            connection = duckdb.connect()
            try:
                names = connection.execute(
                    "SELECT id FROM read_parquet(?) ORDER BY id",
                    [str(local)],
                ).fetchall()
            finally:
                connection.close()
        self.assertEqual(staged["row_count"], 2)
        self.assertEqual(staged["duplicate_count"], 1)
        self.assertEqual([row[0] for row in names], ["/company/00000001", "/company/00000002"])


class PublishTest(unittest.TestCase):
    def test_one_message_per_changed_row(self) -> None:
        publisher = FakePublisher()
        count = publish_rows(
            publisher,
            "projects/example-project/topics/raw-items",
            [
                {"id": "/company/1", "data": '{"company_name": "Acme"}'},
                {"id": "/company/2", "data": '{"company_name": "Beta"}'},
            ],
            destination_table="example-project.raw.items",
        )
        self.assertEqual(count, 2)
        first = publisher.messages[0]
        self.assertEqual(first["topic"], "projects/example-project/topics/raw-items")
        self.assertEqual(first["attributes"]["id"], "/company/1")
        body = json.loads(first["data"])
        self.assertEqual(body["schema_version"], 1)
        self.assertEqual(body["change_type"], "upsert")
        self.assertEqual(body["data"]["company_name"], "Acme")
        self.assertEqual(body["destination_table"], "example-project.raw.items")

    def test_oversized_record_omits_the_body(self) -> None:
        publisher = FakePublisher()
        huge = json.dumps({"blob": "x" * (10 * 1024 * 1024)})
        count = publish_rows(
            publisher,
            "projects/p/topics/t",
            [{"id": "1", "data": huge}],
            destination_table="p.raw.t",
        )
        self.assertEqual(count, 1)
        body = json.loads(publisher.messages[0]["data"])
        self.assertTrue(body["data_omitted"])
        self.assertNotIn("data", body)

    def test_topic_path_accepts_a_short_name_only_with_a_project(self) -> None:
        self.assertEqual(
            topic_path("raw-items", "example-project"), "projects/example-project/topics/raw-items"
        )
        self.assertEqual(
            topic_path("projects/example-project/topics/raw-items", None),
            "projects/example-project/topics/raw-items",
        )
        with self.assertRaises(IngestConfigError):
            topic_path("raw-items", None)


if __name__ == "__main__":
    unittest.main()
