# Staging

One folder per source: `staging/<source>/` containing `_<source>__sources.yml`, `_<source>__models.yml` and `stg_<source>__<entity>.sql`.

Raw tables are `(id, data JSON)`; staging extracts and types the fields. SQL only.
