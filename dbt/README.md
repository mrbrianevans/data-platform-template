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

- `models/staging/<source>/`: `stg_<source>__<entities>`; types the `(id, data JSON)` raw tables. Views.
- `models/intermediate/`: `int_<entity>_<verb>`. Views.
- `models/marts/`: `fct_*` / `dim_*`. Tables.
- `checks/`: dbt v2 project checks that enforce the conventions.
- `macros/`: macros, documented in `_macros.yml`.
- `seeds/`: lookup tables. `seeds/sample_data/` is raw-shaped sample data, off unless `--vars '{load_sample_data: true}'`.
- `.sqlfluff`: SQL style config used by `dbt format` and `dbt lint`.

No Python models.

## Style and conventions

All models follow the [Fivetran dbt SQL guidelines](https://github.com/fivetran/dbt_style_guide/blob/main/sql_guidelines.md) and [dbt Labs best practices](https://docs.getdbt.com/best-practices?version=2). See [`docs/dbt-style-guide.md`](../docs/dbt-style-guide.md) for the rules, examples and a new-model checklist.

```bash
dbt format --profiles-dir .      # apply layout (add --check in CI)
dbt lint --profiles-dir .        # SQL rules
dbt check --profiles-dir .       # project structure/naming/testing rules
dbt parse --profiles-dir .
```

## Notes

dbt v2 does not support DuckDB, so CI runs format, lint, check and parse (all offline) rather than building seeds.
