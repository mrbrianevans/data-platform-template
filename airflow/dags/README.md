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
uv run ruff check .     # lint, including Airflow's AIR ruleset
uv run ruff format      # format (uv run ruff format --check to verify)
```

Format Python with `uv run ruff format` before committing. It uses the ruff version pinned in `uv.lock`, at line length 110 to match Airflow's own style.

