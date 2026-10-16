# Cloud Run jobs

Only for sources that need parallelism (e.g. Microsoft 365). Everything else is an Airflow DAG.

Each job is a Bun + TypeScript entrypoint at `cloud-run/jobs/<name>/index.ts` (add a `package.json` next to it if it has dependencies). There is no Dockerfile per job: `cloud-run/build.ts` defines it.

```bash
cd cloud-run
bun install
bun run build                  # builds local/<name>:latest for every job
bun run build.ts my-job        # only my-job
bun run build.ts --dry-run     # list what would be built
IMAGE_PREFIX=europe-west2-docker.pkg.dev/<project>/<repo> IMAGE_TAG=<sha> bun run build:push
```

Deploy with `terraform/modules/cloud-run-job`.
