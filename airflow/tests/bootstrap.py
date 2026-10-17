"""Put the Dag folder on ``sys.path`` and keep Airflow's home off the real one."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

DAGS = Path(__file__).resolve().parents[1] / "dags"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(DAGS) not in sys.path:
    sys.path.insert(0, str(DAGS))

if "AIRFLOW_HOME" not in os.environ:
    os.environ["AIRFLOW_HOME"] = tempfile.mkdtemp(prefix="airflow-ingest-home-")
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault(
    "AIRFLOW__LOGGING__BASE_LOG_FOLDER",
    str(Path(os.environ["AIRFLOW_HOME"]) / "logs"),
)
