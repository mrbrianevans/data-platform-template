# dbt style guide and conventions

This repo follows two external guides. Follow them whenever you add or change a dbt model, source, test, seed or macro:

1. [Fivetran dbt SQL guidelines](https://github.com/fivetran/dbt_style_guide/blob/main/sql_guidelines.md)
2. [dbt Labs best practices (v2)](https://docs.getdbt.com/best-practices?version=2), in particular [how we structure](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview?version=2) and [how we style](https://docs.getdbt.com/best-practices/how-we-style/0-how-we-style-our-dbt-projects?version=2) our dbt projects, and [best practices for workflows](https://docs.getdbt.com/best-practices/best-practice-workflows?version=2).

The rules below summarise both guides and record how we resolve the places where they differ. If something here is unclear, the linked guides are authoritative. Where the two guides disagree, the stricter rule wins.

## Where the guides differ

| Topic | Fivetran | dbt Labs | We use |
| --- | --- | --- | --- |
| Line length | 150 | 80 | 80 |
| Indentation | tab (4 spaces) | 4 spaces | 4 spaces (YAML: 2) |
| Dates | `date_day` for report dates | `<event>_date` | `<event>_date`; `date_day` only for date-spine/report dates |
| Timestamps | `<event>_at` | `<event>_at`, UTC | `<event>_at`, UTC |
| Table aliases | none unless joining a table to itself | avoid, never initialisms | none unless joining a table to itself |
| Final model names | `<package>__<model>` | entity name, plural | `fct_<entity>` / `dim_<entity>` (see below) |
| Group by | not specified | `group by 1, 2` | `group by 1, 2` |
| Not equal | `!=` | not specified | `!=` |

## Project structure

```
models/
├── staging/<source>/        source-conformed, one folder per source system
│   ├── _<source>__sources.yml
│   ├── _<source>__models.yml
│   └── stg_<source>__<entity>.sql
├── intermediate/<area>/     business-conformed building blocks
│   ├── _int_<area>__models.yml
│   └── int_<entity>_<verb>.sql
└── marts/<area>/            business entities, exposed to users
    ├── _<area>__models.yml
    └── fct_<entity>.sql / dim_<entity>.sql
```

- Only use sub-folders in `intermediate/` and `marts/` once there are around 10 models; until then keep them flat and name the YAML after the directory (`_marts__models.yml`). Staging always has a folder per source.
- **Do not** group staging by loader (Fivetran, Datastream, Airflow) or by business area. Group by source system.
- Config per folder: one `_<directory>__models.yml` (and `_<directory>__sources.yml` for staging) per directory. Doc blocks go in `_<directory>__docs.md`. Leading underscore sorts them to the top.
- Defaults (materialization, schema) are set per folder in `dbt_project.yml`; set config on a model only for exceptions. Prefer folders over tags for selection (`dbt build --select staging+`).
- Use `ref()` for models and `source()` for raw data. Never reference `schema.table` directly.
- `seeds/` is for lookup tables only. Never load source data with seeds. The sample raw data in `seeds/sample_data/` is disabled unless `--vars '{load_sample_data: true}'`.
- Macros live in `macros/` and are documented in `macros/_macros.yml`.
- SQL only: no Python models.

### Layers

| Layer | Prefix | Materialization | Dataset (prod) | Rules |
| --- | --- | --- | --- | --- |
| Staging | `stg_<source>__<entity>` | view | `staging` | One model per raw table, the only place `source()` is used. Rename, type cast, basic computation, categorising. No joins, no aggregations. |
| Intermediate | `int_<entity>_<verb>` | view | `intermediate` | Joins, re-graining, isolating complex logic. Not exposed to end users. Many inputs, ideally one output. |
| Marts | `fct_*` / `dim_*` | table (incremental only when needed) | `marts` | One entity at one grain, wide and denormalised. Bring together at most 4 or 5 concepts; add intermediate models beyond that. |

Start with a view, move to a table when it is slow to query, and to incremental only when the table is slow to build.

Staging details:

- The entity is plural (`stg_xero__invoices`). The double underscore separates source and entity.
- Raw tables are `(id, data JSON)`. Staging extracts fields from `data`, renames them to business terms (`customer_id` not `user_id` if the business says customer), and casts them.
- If joins are needed to stage a concept (for example unioning identical sources or joining a delete table), put `base_<source>__<entity>` models in `staging/<source>/base/` and join them in the `stg_` model.
- Mart naming departs from dbt Labs' bare entity names (`customers`) in favour of `fct_` / `dim_` prefixes, which both guides accept for signalling which relations users should query. Never build the same concept per team (`finance_orders` vs `marketing_orders`).

## Naming

- `snake_case` everywhere; underscores, never dots, in model names. No abbreviations (`customer`, not `cust`) and no reserved words as names.
- Every model has a primary key named `<entity>_id` (for example `invoice_id`), as a string. Use the same name for the same key in every model.
- Booleans: `is_` or `has_` prefix (`is_deleted`, `has_orders`).
- Timestamps: `<event>_at`, in UTC, past tense (`created_at`). Use a suffix if another timezone is unavoidable (`created_at_pt`).
- Dates: `<event>_date` (`created_date`). `date_day` is only for report/date-spine columns.
- Money in decimal currency (`19.99`). If not, say so in the name (`price_in_cents`).
- Versioned models use `_v1`, `_v2`.
- Order columns by type: ids, strings, numerics, booleans, dates, timestamps, with a `---------- ids` style comment header in staging.

## SQL style

Formatting is enforced by `dbt format` and `dbt lint` using [`dbt/.sqlfluff`](../dbt/.sqlfluff). Both commands are built on SQLFluff: `dbt format` applies SQLFluff's layout rules (the `LT*` family) and `dbt lint` reports the rest of the rules, with the same `.sqlfluff` config. They do not use sqlfmt.

- Everything lowercase: keywords, functions, identifiers, CTE names.
- Four-space indent, trailing commas, lines of at most 80 characters.
- `select` list starts on the line after `select`; one column per line. `case` lines up with `end` and each `when` has its own line.
- Start `and` / `or` / operators on the next line.
- Use `!=` not `<>`; `where not is_deleted` not `where is_deleted = false`.
- Always write `as` for column, expression and table aliases. Never use a reserved word as an alias.
- Use CTEs, not subqueries, and break complicated selects into small CTEs, each doing one logical unit of work. Name CTEs for what they do (`orders_joined_to_customers`).
- Import CTEs: every `ref()`, `source()` and `var()` appears in a CTE at the top of the file, named after the thing it imports, selecting only what is needed. The last line of a model is `select * from <final_cte>`.
- Joins: always state the join type (`inner join`, `left join`); use `join ... on`, not `using`; move left to right (avoid `right join`); prefix every column with its table name when more than one table is involved; no table aliases unless joining a table to itself.
- Fields before aggregates and window functions. Aggregate as early as possible, before joining. `group by 1, 2`.
- Prefer `union all` to `union`; prefer `where` to `having`; avoid `order by` in models.
- Cross-database syntax: `coalesce` not `ifnull`/`nvl`, `case when` not `iff`/`if`, `is null` / `is not null` not `isnull()`. Cast timestamps explicitly in staging (`{{ dbt.type_timestamp() }}` / `cast(... as timestamp)`).
- Models must build on both BigQuery (`dev`/`prod`) and DuckDB (`ci`). Use `dbt.type_*()` macros for types and the `json_string()` macro in `dbt/macros/` for extracting fields from raw JSON, rather than adapter-specific functions. Add a dispatching macro when you need another adapter-specific function.
- Comments only where logic is important or complex; leave blank lines around the commented code. Use Jinja comments (`{# #}`) when the comment should not reach compiled SQL.
- CTEs duplicated across models become intermediate models.
- Jinja: spaces inside delimiters (`{{ ref('x') }}`), 4-space indent inside blocks, do not nest curlies.
- In-model config only for exceptions, written as:

```sql
{{
    config(
        materialized = 'incremental',
        unique_key = 'invoice_id'
    )
}}
```

### YAML style

- Two-space indent, indented lists, lines of at most 80 characters, blank line between list items that are dictionaries. Format with Prettier.
- Every model has a description, and every model's primary key is tested `unique` and `not_null`.

```yaml
version: 2

models:
  - name: stg_example__items
    description: Items from the example source, one row per item.
    columns:
      - name: item_id
        description: Primary key.
        data_tests:
          - unique
          - not_null

      - name: item_amount
        description: Item value in pounds.
```

## Example staging model

```sql
with

source as (

    select * from {{ source('example', 'raw_example__items') }}

),

renamed as (

    select
        ---------- ids
        cast(id as {{ dbt.type_string() }}) as item_id,

        ---------- strings
        {{ json_string('data', 'name') }} as item_name,

        ---------- numerics
        cast({{ json_string('data', 'amount') }} as {{ dbt.type_numeric() }})
            as item_amount

    from source

)

select * from renamed
```

## Example mart

```sql
with

orders as (

    select * from {{ ref('stg_example__orders') }}

),

customers as (

    select * from {{ ref('stg_example__customers') }}

),

orders_joined_to_customers as (

    select
        orders.order_id,
        orders.customer_id,
        customers.customer_name,

        -- Customers on a discount plan pay the discounted amount
        orders.order_amount * customers.discount_rate as order_total,

        orders.is_cancelled,
        orders.ordered_at
    from orders
    left join customers
        on orders.customer_id = customers.customer_id
    where
        not orders.is_deleted
        and orders.ordered_at >= '2021-01-01'

)

select * from orders_joined_to_customers
```

## Warehouse layout

Each layer builds into its own BigQuery dataset: `staging`, `intermediate`, `marts` in the `prod` target (and the `ci` DuckDB target), and `dbt_<name>_staging` etc. in other targets (see `dbt/macros/generate_schema_name.sql`). Raw data is in `raw`. Use `dev` locally and `prod` only from deployment.

## Enforcement

Run these from `dbt/` before committing. CI runs the same commands.

| Command | What it enforces |
| --- | --- |
| `dbt format` / `dbt format --check` | SQL layout (indent, commas, line length, case) from `.sqlfluff` |
| `dbt lint` | SQL rules: aliasing, joins, subqueries, `union all`, `!=`, and so on |
| `dbt check` | Project rules in `dbt/checks/`: descriptions, primary key tests, layer naming and folders, staging reads sources only, only staging reads sources, properties file naming |
| `dbt parse` | The project compiles |
| `dbt build -t ci --vars '{load_sample_data: true}'` | Models and tests run on DuckDB against the sample seeds (no warehouse needed) |

Static analysis defaults to `baseline`. Develop with `DBT_ENV_STATIC_ANALYSIS=strict` (requires `dbt login`) and leave it unset in deployment, per [dbt's recommendation](https://docs.getdbt.com/best-practices/optimize-static-analysis-for-development-and-deployment).

If you need to deviate from a rule, change the check or `.sqlfluff` in the same pull request and note the reason here. Consistency matters more than any individual rule.

## Checklist for a new model

1. Right folder and name for its layer (see above); source folder for staging.
2. Imports at the top (`ref` / `source` in CTEs), `select * from <final_cte>` at the bottom.
3. Columns named and ordered per the naming rules; primary key `<entity>_id`.
4. Entry in the folder's `_<directory>__models.yml` with a description and `unique` + `not_null` on the primary key. New sources also get `_<source>__sources.yml` and a `docs/connectors/<source>.md` page.
5. `dbt format`, `dbt lint`, `dbt check`, `dbt parse` all pass, and `dbt build -t ci` passes (add sample seed rows in `seeds/sample_data/` for new sources).
