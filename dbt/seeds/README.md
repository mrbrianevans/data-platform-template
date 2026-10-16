# Seeds

Seeds are for lookup tables that do not exist in any source system. Never load source data with seeds.

`sample_data/` holds raw-shaped samples (`raw_<source>__<entity>`, columns `(id, data)`) for local development only. It is disabled by default: `dbt seed --vars '{load_sample_data: true}'`.
