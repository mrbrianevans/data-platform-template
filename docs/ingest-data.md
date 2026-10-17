# ingest_data

`ingest_data` is the shared Airflow task group every dataset Dag calls once its files are already in Google Cloud Storage. It lives in `airflow/dags/ingest_data` and is imported with `from ingest_data import ingest_data`. Managed Airflow in this platform is Cloud Composer; the group is written for the Airflow 3 line pinned in `airflow/pyproject.toml`.

A typical caller paginates a third-party API, writes the response as NDJSON in GCS, then calls the group. The group does not fetch from the API and it does not unzip. File names change every release, so the caller passes URIs or globs and never a hard-coded object name.

## Why `(id, data)`

Every raw table is two columns:

| column | type | meaning |
| --- | --- | --- |
| `id` | `STRING` | identity of the source record |
| `data` | `JSON` | the whole source record |

The ingest schema does not change when the source adds or removes a field. dbt staging is where columns are typed. That is also why NDJSON is read with DuckDB `read_ndjson_objects`: each line stays one JSON value and is never parsed against a schema.

## Parameters

| parameter | required | meaning |
| --- | --- | --- |
| `group_id` | yes | task group id, unique in the Dag |
| `source_uris` | yes | one `gs://` URI, a list of them, or globs (`*`, `?`, `[`). A URI ending in `/` means every object under that prefix. Templated (`{{ ds }}` and so on) |
| `destination_table` | yes | `project.dataset.table`, or `dataset.table` when `project_id` is set. Created if missing. Templated |
| `pubsub_topic` | yes | `projects/<project>/topics/<topic>`, or a topic id when `project_id` is set. One topic per dataset. Templated |
| `file_format` | no | `auto` (default), `ndjson`, `json_array`, `csv` or `parquet`. `auto` uses the suffix, then the first bytes |
| `id_columns` | no | JSON keys that form the id. One column is used as-is. Several are joined with `\|`, so bank holidays pass `["division", "date"]` and become `england-and-wales\|2024-01-01`. A missing key fails the task |
| `id_expression` | no | a single DuckDB expression over the JSON column `data`, for example `json_extract_string(data, '$.resource_uri')` or `lower(json_extract_string(data, '$.organisation_number'))`. Do not pass this and `id_columns` together |
| `project_id` | no | billing project, and the project used when the table or topic is not fully qualified |
| `location` | no | BigQuery location. Default `europe-west2` |
| `gcp_conn_id` | no | Composer connection. Default `google_cloud_default` |
| `staging_prefix` | no | `gs://` object path, or a prefix ending in `/`, for the normalised Parquet. Default is `_ingest/<dag>/<run>/<group>/normalised.parquet` in the first source bucket |
| `csv_delimiter` | no | default `,` |
| `csv_header` | no | default `True` |
| `csv_encoding` | no | passed through to DuckDB when set |

If neither `id_columns` nor `id_expression` is set, the id is `sha256` of the JSON text. That is the fallback for a file with no natural key, such as the Companies House ACSP CSV.

Ids used by the first sources:

| source | format | id |
| --- | --- | --- |
| Companies House (Companies Catalogue) | NDJSON | `resource_uri` |
| Charity Commission direct JSON | JSON array | `organisation_number` |
| GOV.UK bank holidays | CSV or NDJSON, after the caller has flattened events | `division` and `date` |
| ONS Postcode Directory | CSV | caller chooses the column, often `pcds` |
| Companies House ACSP list | CSV | row hash (omit the id arguments) |

CSV fields are read as text, so a postcode or code with a leading zero is not turned into a number. Empty fields stay empty strings. Compressed objects (`.gz`, `.zip`, and similar) are rejected; the caller unzips first.

When the same id appears more than once in the batch, the last row is kept. Order is the order of `source_uris`, and within a glob the object name order.

## The four steps

The group is six tasks. Diff and merge are split so a publish retry still has the diff, and merge can be retried on its own.

1. **Normalise.** Download the matched objects, read them with DuckDB, and write Parquet of `(id, data)` where `data` is a JSON string. Upload that Parquet to the staging URI. The worker needs disk and memory for the largest file.
2. **Load.** Load the Parquet into a temporary BigQuery table in the destination dataset (`_ingest_<group>_<digest>_stage`). The load truncates that table, so a retry replaces it. `data` is still a string at this point.
3. **Diff and merge.** Create the target `(id STRING NOT NULL, data JSON NOT NULL)` if it does not exist. Build `_ingest_<group>_<digest>_diff` with the rows whose id is new, or whose `SHA256(TO_JSON_STRING(data))` differs from the target. `TO_JSON_STRING` canonicalises key order, so a source that re-serialises the same record is not a change. `MERGE` the diff into the target (`UPDATE` when the id exists, `INSERT` otherwise). Rows that vanished from the file are not deleted; this is not a snapshot replace.
4. **Publish.** Read the same diff table and publish one Pub/Sub message per row. Then delete the stage table, the diff table and the staging Parquet. Both temp tables also expire after a day, so a failed run does not leave them forever.

Publishing does not delete the diff. If publish fails, the retry reads the same diff and sends the events again. Consumers should treat `id` as an idempotency key. A message looks like:

```json
{
  "schema_version": 1,
  "id": "/company/00000001",
  "destination_table": "project.raw.companies_house",
  "change_type": "upsert",
  "data": {"resource_uri": "/company/00000001", "company_name": "Acme Ltd"}
}
```

Attributes `id` and `destination_table` are set when they fit in Pub/Sub's attribute size limit. A record whose JSON would exceed 9MiB is sent without `data` and with `"data_omitted": true`.

Clearing the diff task after a successful merge rebuilds the diff against the table that already has the rows, so the new diff is empty and the events are not sent again. Re-run publish on its own when the events are what failed.

## What the caller does not get from this group

The dataset and the Pub/Sub topic must already exist. The task group creates the raw table only. The Composer service account needs to read the source objects, write and delete the staging Parquet, create and update BigQuery tables and jobs in `location`, and publish to the topic.

`example_ingest` in `airflow/dags/example_ingest.py` is a tiny unscheduled Dag that shows the call. It is not a connector and it points at a bucket that does not exist.
