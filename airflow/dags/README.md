# DAGs

- One DAG per source: `<source>.py`.
- `dbt_build.py`: runs the dbt project after ingestion.
- `ingest_data/`: shared package (task group) imported by each DAG with `from ingest_data import ...`. Put other shared code in packages alongside it.

## Dependencies

Managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`).

```bash
cd airflow
uv sync                 # install
uv add <package>        # add a dependency
uv run ruff check .     # lint
```
