"""BigQuery SQL and client calls. The client is the in-memory fake."""

from __future__ import annotations

import unittest

import bootstrap  # noqa: F401
from fakes import FakeBigQuery

from ingest_data.bigquery import create_target_and_diff, delete_tables, load_parquet, merge_diff
from ingest_data.sql import IngestConfigError, qualified_table, temporary_table_ids


class SqlAndLoadTest(unittest.TestCase):
    def test_identifiers_quote_a_hyphenated_project_and_reject_injection(self) -> None:
        self.assertEqual(
            qualified_table("example-project.raw.items"),
            "`example-project`.`raw`.`items`",
        )
        self.assertEqual(
            qualified_table("raw.items", project_id="example-project"),
            "`example-project`.`raw`.`items`",
        )
        with self.assertRaises(IngestConfigError):
            qualified_table("raw.items`; drop table raw.items; --")

    def test_temp_tables_are_stable_per_run_and_differ_across_runs(self) -> None:
        kwargs = {
            "destination_table": "example-project.raw.items",
            "project_id": "example-project",
            "dag_id": "example_ingest",
            "group_id": "ingest_items",
            "run_id": "manual__2024-01-01T00:00:00+00:00",
        }
        first = temporary_table_ids(**kwargs)
        again = temporary_table_ids(**kwargs)
        other = temporary_table_ids(**{**kwargs, "run_id": "manual__2024-01-02T00:00:00+00:00"})
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertTrue(first[0].endswith("_stage"))
        self.assertTrue(first[1].endswith("_diff"))
        self.assertNotIn("+", first[0])
        self.assertNotIn(":", first[0])

    def test_load_sets_schema_truncate_and_expiry(self) -> None:
        client = FakeBigQuery()
        load_parquet(client, "gs://bucket/file.parquet", "example-project.raw._ingest_stage")
        load = client.loads[0]
        self.assertEqual(load["uri"], "gs://bucket/file.parquet")
        self.assertEqual(load["write_disposition"], "WRITE_TRUNCATE")
        self.assertEqual(load["source_format"], "PARQUET")
        self.assertEqual(load["schema"], [("id", "STRING", "NULLABLE"), ("data", "STRING", "NULLABLE")])
        self.assertEqual(client.updated, ["expires"])

    def test_diff_creates_the_target_then_the_hash_diff_then_merge_uses_it(self) -> None:
        client = FakeBigQuery()
        create_target_and_diff(
            client,
            stage_table="example-project.raw._ingest_stage",
            diff_table="example-project.raw._ingest_diff",
            destination_table="example-project.raw.items",
            project_id="example-project",
        )
        create_sql, diff_sql = client.queries
        self.assertIn("CREATE TABLE IF NOT EXISTS `example-project`.`raw`.`items`", create_sql)
        self.assertIn("id STRING NOT NULL", create_sql)
        self.assertIn("data JSON NOT NULL", create_sql)
        self.assertIn("CREATE OR REPLACE TABLE `example-project`.`raw`.`_ingest_diff`", diff_sql)
        self.assertIn("PARSE_JSON(data, wide_number_mode => 'round')", diff_sql)
        self.assertIn("LEFT JOIN `example-project`.`raw`.`items`", diff_sql)
        self.assertIn("SHA256(TO_JSON_STRING(incoming.data))", diff_sql)
        self.assertIn("expiration_timestamp", diff_sql)

        merge_diff(
            client,
            diff_table="example-project.raw._ingest_diff",
            destination_table="example-project.raw.items",
            project_id="example-project",
        )
        merge = client.queries[-1]
        self.assertIn("MERGE `example-project`.`raw`.`items`", merge)
        self.assertIn("USING `example-project`.`raw`.`_ingest_diff`", merge)
        self.assertIn("WHEN MATCHED THEN", merge)
        self.assertIn("WHEN NOT MATCHED THEN", merge)
        self.assertNotIn("_ingest_stage", merge)

    def test_delete_tables_records_both_and_raises_after_trying_the_rest(self) -> None:
        client = FakeBigQuery()
        client.fail_deletes.add("example-project.raw._ingest_stage")
        with self.assertRaises(RuntimeError):
            delete_tables(
                client,
                ["example-project.raw._ingest_stage", "example-project.raw._ingest_diff"],
            )
        self.assertEqual(client.deleted, ["example-project.raw._ingest_diff"])


if __name__ == "__main__":
    unittest.main()
