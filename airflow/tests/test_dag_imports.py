from pathlib import Path

import pytest

airflow = pytest.importorskip("airflow")

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"


def test_dags_import_without_errors():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert dag_bag.import_errors == {}
