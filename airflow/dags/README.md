# DAGs

- One DAG per source: `<source>.py`.
- `dbt_build.py`: runs the dbt project after ingestion.
- `ingest_data/`: shared task group imported by each DAG with `from ingest_data import ingest_data`. Parameters, the four steps and the `(id, data)` layout are in [`docs/ingest-data.md`](../../docs/ingest-data.md). `example_ingest.py` shows a call; it is not a source connector. Put other shared code in packages alongside `ingest_data`.

## Dependencies

Managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`).

```bash
cd airflow
uv sync                 # install
uv add <package>        # add a dependency
uv run ruff check .     # lint, including Airflow's AIR ruleset
uv run ruff format      # format (uv run ruff format --check to verify)
uv run python -m unittest discover -s tests -v
```

Format Python with `uv run ruff format` before committing. It uses the ruff version pinned in `uv.lock`, at line length 110 to match Airflow's own style.

