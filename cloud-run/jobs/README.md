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

## TypeScript

Once a Cloud Run job or service is written in TypeScript, check it with Bun's built-in typechecker, formatter, and linter, from `cloud-run/`:

```bash
bun check         # typecheck (nearest tsconfig; same errors as tsc)
bun lint          # lint
bun fmt           # format
bun fmt --check   # format check, for CI
```

Docs: [type checking](https://bun.com/docs/runtime/check), [linter](https://bun.com/docs/lint), [formatter](https://bun.com/docs/format).

These commands are not part of CI yet. `.github/workflows/images.yml` still runs `bunx tsc` and `bun run build`. Switch that workflow to `bun check`, `bun lint`, and `bun fmt --check` when the first TypeScript job or service lands.

`bun check` ships in Bun 1.4. `bun lint` and `bun fmt` are documented, and they are not subcommands in Bun 1.4.3 (the current release): that version treats the names as `package.json` scripts. Keep `lint` and `fmt` out of `package.json` scripts so a later Bun release runs the built-ins. A `lint` or `fmt` script, when present, is what `bun lint` and `bun fmt` execute.
