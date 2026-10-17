# bigquery

BigQuery datasets in the London region:

| Dataset | Contents |
| --- | --- |
| `raw` | Landed source rows (`id`, `data` JSON) |
| `staging` | Typed staging models (`stg_*`) |
| `intermediate` | Intermediate models (`int_*`) |
| `marts` | Mart models (`fct_*` / `dim_*`) |
| `analytics` | dbt `prod` target dataset |

Layer models set `+schema`, so in the `prod` target they are created in `staging`, `intermediate`, and `marts` rather than `analytics`. `analytics` is the profile's default dataset.

## Files

- `main.tf` resources
- `variables.tf` inputs
- `outputs.tf` outputs
