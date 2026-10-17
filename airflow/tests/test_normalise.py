"""DuckDB normalisation against local sample files. No GCP client is opened."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import bootstrap
import duckdb

from ingest_data.normalise import FileFormat, normalise_files, resolve_format, scan_sql
from ingest_data.sql import IngestConfigError, build_id_expression

FIXTURES = bootstrap.FIXTURES


def _rows(path: Path) -> list[tuple[str, dict]]:
    connection = duckdb.connect()
    try:
        raw = connection.execute(
            "SELECT id, data FROM read_parquet(?) ORDER BY id",
            [str(path)],
        ).fetchall()
    finally:
        connection.close()
    return [(row[0], json.loads(row[1])) for row in raw]


class NormaliseSampleFilesTest(unittest.TestCase):
    def test_ndjson_keeps_the_whole_record_and_the_last_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.parquet"
            result = normalise_files(
                [("companies_house.ndjson", FIXTURES / "companies_house.ndjson")],
                output,
                file_format="ndjson",
                id_columns=["resource_uri"],
            )
            rows = dict(_rows(output))

        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(rows["/company/00000001"]["company_name"], "Acme Limited")
        self.assertEqual(rows["/company/00000002"]["sic_codes"], ["88990"])
        self.assertEqual(rows["/company/00000002"]["company_name"], "Beta CIC")

    def test_json_array_uses_organisation_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.parquet"
            result = normalise_files(
                [("charity_commission.json", FIXTURES / "charity_commission.json")],
                output,
                file_format="json_array",
                id_columns=["organisation_number"],
            )
            rows = dict(_rows(output))

        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.duplicate_count, 0)
        self.assertEqual(rows["1000001"]["name"], "Harbour Trust")
        self.assertEqual(rows["1000002"]["activities"], ["education", "relief"])

    def test_auto_detects_a_json_array_and_ndjson(self) -> None:
        self.assertEqual(
            resolve_format(FIXTURES / "charity_commission.json", "auto"),
            FileFormat.JSON_ARRAY,
        )
        self.assertEqual(
            resolve_format(FIXTURES / "companies_house.ndjson", "auto"),
            FileFormat.NDJSON,
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.parquet"
            result = normalise_files(
                [("charity_commission.json", FIXTURES / "charity_commission.json")],
                output,
                file_format="auto",
                id_columns=["organisation_number"],
            )
        self.assertEqual(result.row_count, 2)

    def test_bank_holidays_join_division_and_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.parquet"
            normalise_files(
                [("bank_holidays.csv", FIXTURES / "bank_holidays.csv")],
                output,
                file_format="csv",
                id_columns=["division", "date"],
            )
            rows = dict(_rows(output))

        self.assertEqual(
            set(rows),
            {
                "england-and-wales|2024-01-01",
                "scotland|2024-01-02",
                "england-and-wales|2024-12-25",
            },
        )
        self.assertEqual(rows["england-and-wales|2024-01-01"]["title"], "New Year's Day")

    def test_csv_keeps_leading_zeros_and_hashes_the_row_when_no_id_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.parquet"
            second = Path(tmp) / "second.parquet"
            one = normalise_files(
                [("acsp.csv", FIXTURES / "acsp.csv")],
                first,
                file_format="csv",
            )
            two = normalise_files(
                [("acsp.csv", FIXTURES / "acsp.csv")],
                second,
                file_format="csv",
            )
            rows = _rows(first)

        self.assertEqual(one, two)
        self.assertEqual(len(rows), 2)
        ids = {row[0] for row in rows}
        self.assertTrue(all(len(value) == 64 and value.isalnum() for value in ids))
        stored = {row[1]["acsp_number"]: row[1] for row in rows}
        self.assertEqual(stored["0123"]["business_name"], "North Books")
        self.assertIsInstance(stored["0123"]["acsp_number"], str)

    def test_changed_row_changes_the_hash_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.csv"
            changed = Path(tmp) / "changed.csv"
            original.write_text("business_name,acsp_number\nNorth Books,0123\n", encoding="utf-8")
            changed.write_text("business_name,acsp_number\nNorth Books,9999\n", encoding="utf-8")
            left = Path(tmp) / "left.parquet"
            right = Path(tmp) / "right.parquet"
            normalise_files([("original.csv", original)], left, file_format="csv")
            normalise_files([("changed.csv", changed)], right, file_format="csv")
            left_id = _rows(left)[0][0]
            right_id = _rows(right)[0][0]
        self.assertNotEqual(left_id, right_id)

    def test_pipe_delimited_csv_and_parquet_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "holidays.psv"
            source.write_text(
                "division|date\nengland-and-wales|2024-01-01\n",
                encoding="utf-8",
            )
            csv_output = Path(tmp) / "from_csv.parquet"
            normalise_files(
                [("holidays.psv", source)],
                csv_output,
                file_format="csv",
                csv_delimiter="|",
                id_columns=["division"],
            )
            self.assertEqual(_rows(csv_output)[0][0], "england-and-wales")

            parquet_source = Path(tmp) / "source.parquet"
            connection = duckdb.connect()
            try:
                connection.execute(
                    """
                    COPY (
                        SELECT 'england-and-wales' AS division, '2024-01-01' AS date
                    ) TO ? (FORMAT PARQUET)
                    """,
                    [str(parquet_source)],
                )
            finally:
                connection.close()
            output = Path(tmp) / "out.parquet"
            normalise_files(
                [("source.parquet", parquet_source)],
                output,
                file_format="parquet",
                id_columns=["division"],
            )
            rows = dict(_rows(output))
        self.assertEqual(rows["england-and-wales"]["date"], "2024-01-01")

    def test_later_file_wins_when_ids_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.ndjson"
            second = Path(tmp) / "b.ndjson"
            first.write_text('{"resource_uri": "/company/1", "name": "old"}\n', encoding="utf-8")
            second.write_text('{"resource_uri": "/company/1", "name": "new"}\n', encoding="utf-8")
            output = Path(tmp) / "out.parquet"
            result = normalise_files(
                [("a.ndjson", first), ("b.ndjson", second)],
                output,
                file_format="ndjson",
                id_columns=["resource_uri"],
            )
            rows = dict(_rows(output))
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(rows["/company/1"]["name"], "new")

    def test_missing_id_fails_and_names_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.parquet"
            with self.assertRaises(IngestConfigError) as raised:
                normalise_files(
                    [("bank_holidays.csv", FIXTURES / "bank_holidays.csv")],
                    output,
                    file_format="csv",
                    id_columns=["organisation_number"],
                )
        self.assertIn("bank_holidays.csv", str(raised.exception))

    def test_json_object_is_not_accepted_as_an_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "one.json"
            source.write_text('{"organisation_number": "1"}\n', encoding="utf-8")
            with self.assertRaises(IngestConfigError) as raised:
                normalise_files(
                    [("one.json", source)],
                    Path(tmp) / "out.parquet",
                    file_format="json_array",
                    id_columns=["organisation_number"],
                )
        self.assertIn("not a top-level array", str(raised.exception))

    def test_compressed_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "items.csv.gz"
            source.write_text("a\n1\n", encoding="utf-8")
            with self.assertRaises(IngestConfigError) as raised:
                normalise_files(
                    [("items.csv.gz", source)],
                    Path(tmp) / "out.parquet",
                    file_format="csv",
                )
        self.assertIn("Unzip", str(raised.exception))

    def test_ndjson_reader_does_not_infer_a_schema(self) -> None:
        sql, params = scan_sql(FileFormat.NDJSON)
        self.assertIn("read_ndjson_objects(?)", sql)
        self.assertNotIn("read_json", sql)
        self.assertEqual(params, 1)
        array_sql, _ = scan_sql(FileFormat.JSON_ARRAY)
        self.assertIn("from_json(content, '[\"JSON\"]')", array_sql)

    def test_id_expression_rules(self) -> None:
        self.assertEqual(
            build_id_expression(None, ["division", "date"]),
            "json_extract_string(data, '$.division') || '|' || json_extract_string(data, '$.date')",
        )
        self.assertEqual(build_id_expression(None, None), "sha256(cast(data AS VARCHAR))")
        with self.assertRaises(IngestConfigError):
            build_id_expression("resource_uri", ["resource_uri"])
        with self.assertRaises(IngestConfigError):
            build_id_expression("sha256(data); drop table raw", None)
        with self.assertRaises(IngestConfigError):
            build_id_expression(None, ["division;date"])
        with self.assertRaises(IngestConfigError):
            build_id_expression(None, [])


if __name__ == "__main__":
    unittest.main()
