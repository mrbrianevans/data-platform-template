# dbt

SQL-only dbt project run with **dbt v2** (the dbt Fusion engine, `dbt` 2.x). It is free to download and use, and replaces the Python dbt-core CLI, so there is no Python dependency for this directory.

## Install

```bash
curl -fsSL https://public.cdn.getdbt.com/fs/install/install.sh | sh -s -- --update
exec $SHELL
dbt --version   # dbt 2.x
```

The installer places the binary at `~/.local/bin/dbt` (and an alias `dbtf`). See the [dbt Fusion install docs](https://docs.getdbt.com/docs/fusion/install-fusion) for other platforms. Update later with `dbt system update`.

## Use

`profiles.yml` lives in this directory and targets BigQuery in `europe-west2` using your own gcloud credentials.

```bash
gcloud auth application-default login
export GCP_PROJECT_ID=<project-id>

cd dbt
dbt parse --profiles-dir .          # offline, no warehouse needed
dbt build --profiles-dir .          # seeds, models, tests against BigQuery
```

## Layout

- `models/staging/<source>/`: `stg_<source>__<entity>`; types the `(id, data JSON)` raw tables.
- `models/intermediate/`: `int_*`.
- `models/marts/`: `fct_*` / `dim_*`.
- `seeds/`: sample data.

No Python models.

## Notes

dbt v2 does not support DuckDB, so CI runs `dbt parse` (offline) rather than building seeds locally.
