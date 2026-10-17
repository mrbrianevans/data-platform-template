"""Parse the example Dag. This does not start a scheduler or open a GCP client."""

from __future__ import annotations

import os
import unittest
from datetime import datetime

import bootstrap

os.environ.setdefault("AIRFLOW__CORE__DAGS_FOLDER", str(bootstrap.DAGS))

from airflow.dag_processing.dagbag import DagBag
from airflow.sdk import DAG

from ingest_data import ingest_data
from ingest_data.sql import IngestConfigError

TASK_ORDER = [
    "ingest_items.normalise",
    "ingest_items.load_temp_table",
    "ingest_items.build_diff",
    "ingest_items.merge_changes",
    "ingest_items.publish_changes",
    "ingest_items.cleanup",
]


class DagImportTest(unittest.TestCase):
    def test_example_dag_parses_and_chains_the_four_steps(self) -> None:
        bag = DagBag(dag_folder=str(bootstrap.DAGS))
        self.assertEqual(bag.import_errors, {})
        self.assertIn("example_ingest", bag.dags)
        dag = bag.dags["example_ingest"]
        self.assertEqual(dag.schedule, None)
        self.assertEqual([task.task_id for task in dag.topological_sort()], TASK_ORDER)
        normalise = dag.get_task("ingest_items.normalise")
        self.assertIn("op_args", normalise.template_fields)
        self.assertEqual(normalise.op_args[0], "gs://example-bucket/raw/items/*.ndjson")
        self.assertEqual(normalise.op_args[1]["id_columns"], ["id"])
        self.assertEqual(normalise.op_args[1]["file_format"], "ndjson")

    def test_factory_accepts_an_id_expression_and_rejects_a_bad_format(self) -> None:
        with DAG(
            dag_id="test_ingest_factory",
            start_date=datetime(2024, 1, 1),
            schedule=None,
            catchup=False,
        ):
            ingest_data(
                group_id="ingest_charities",
                source_uris=["gs://bucket/charity/{{ ds }}.json"],
                destination_table="raw.charity_commission",
                pubsub_topic="raw-charity-commission",
                file_format="json_array",
                id_expression="json_extract_string(data, '$.organisation_number')",
                project_id="example-project",
            )
        with (
            DAG(
                dag_id="test_ingest_factory_invalid",
                start_date=datetime(2024, 1, 1),
                schedule=None,
                catchup=False,
            ),
            self.assertRaises(IngestConfigError),
        ):
            ingest_data(
                group_id="ingest_bad",
                source_uris="gs://bucket/file.csv",
                destination_table="example-project.raw.bad",
                pubsub_topic="projects/example-project/topics/bad",
                file_format="xlsx",
            )


if __name__ == "__main__":
    unittest.main()
