#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { extractBundle } from "./archive.mjs";
import { runAudit } from "./audit.mjs";
import { repairIfNeeded } from "./repair.mjs";
import { createRedisClient, loadRegistry } from "./registry.mjs";

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--staging") {
      args.staging = argv[++i];
    } else if (token === "--report") {
      args.report = argv[++i];
    } else if (token === "--manifest") {
      args.manifest = argv[++i];
    } else if (token === "--tenant") {
      args.tenant = argv[++i];
    } else if (token === "--bundle") {
      args.bundle = argv[++i];
    } else {
      args._.push(token);
    }
  }
  return args;
}

async function ensureExtracted(staging, bundle) {
  const extracted = join(staging, "extracted");
  const marker = join(extracted, ".bastion_extracted");
  await mkdir(extracted, { recursive: true });
  if (!existsSync(marker)) {
    await extractBundle(bundle, extracted);
    await writeFile(marker, bundle, "utf8");
  }
  return extracted;
}

async function main() {
  const args = parseArgs(process.argv);
  const command = args._[0];
  if (!command) {
    console.error("usage: bastion-audit <audit|repair> --staging DIR --bundle FILE ...");
    process.exit(2);
  }

  const staging = args.staging ?? "/app/staging";
  const bundle = args.bundle ?? join(staging, "bundle.tar.gz");
  const tenant = args.tenant ?? "prod";
  const extracted = await ensureExtracted(staging, bundle);

  const redis = createRedisClient();
  try {
    const registry = await loadRegistry(redis, tenant);
    if (command === "audit") {
      const report = await runAudit(extracted, registry);
      const out = args.report ?? join(staging, "audit.json");
      await mkdir(dirname(out), { recursive: true });
      await writeFile(out, `${JSON.stringify(report, null, 2)}\n`, "utf8");
      process.exit(report.clean ? 0 : 3);
    }
    if (command === "repair") {
      const manifest = await repairIfNeeded(extracted, registry);
      const out = args.manifest ?? join(staging, "fix_manifest.json");
      await mkdir(dirname(out), { recursive: true });
      await writeFile(out, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
      process.exit(0);
    }
    console.error(`unknown command: ${command}`);
    process.exit(2);
  } finally {
    redis.disconnect();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
