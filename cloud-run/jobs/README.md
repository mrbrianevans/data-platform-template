# Cloud Run jobs

Only for sources that need parallelism (e.g. Microsoft 365). Everything else is an Airflow DAG.

Each job lives in `cloud-run/jobs/<name>/` and is Bun + TypeScript:

```
<name>/
├── Dockerfile
├── package.json
├── tsconfig.json
└── src/index.ts
```

Jobs write NDJSON to GCS in the same shape the `ingest_data` task group expects, and are deployed with `terraform/modules/cloud-run-job`.
