import { $, Glob } from "bun";
import { dirname, join, basename } from "node:path";

const jobsDir = join(import.meta.dir, "jobs");

const dockerfile = `FROM oven/bun:1-slim
WORKDIR /app
COPY . .
RUN if [ -f package.json ]; then bun install --production; fi
USER bun
CMD ["bun", "run", "index.ts"]
`;

const args = process.argv.slice(2);
const push = args.includes("--push");
const dryRun = args.includes("--dry-run");
const only = args.filter((a) => !a.startsWith("--"));

const prefix = process.env.IMAGE_PREFIX ?? "local";
const tag = process.env.IMAGE_TAG ?? "latest";

const found: string[] = [];
for await (const file of new Glob("*/index.ts").scan({ cwd: jobsDir })) {
  found.push(basename(dirname(file)));
}
const jobs = found.sort().filter((name) => only.length === 0 || only.includes(name));

if (jobs.length === 0) {
  console.log(`No jobs found in ${jobsDir} (expected jobs/<name>/index.ts)`);
  process.exit(0);
}

for (const name of jobs) {
  const image = `${prefix}/${name}:${tag}`;
  const context = join(jobsDir, name);
  console.log(`==> ${image}`);

  if (dryRun) continue;

  await $`docker build --tag ${image} --file - ${context} < ${new Response(dockerfile)}`;
  if (push) await $`docker push ${image}`;
}
