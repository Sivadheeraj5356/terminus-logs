import { execFileSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { deriveProvenance } from "./provenance";

interface Arguments {
  journal: string;
  config: string;
  output: string;
  cacheDir: string;
}

interface ReplayPackage {
  provenance: {
    journal_digest: string;
    config_digest: string;
    cache_key: string;
  };
}

function parseArguments(argv: string[]): Arguments {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === undefined || value === undefined || !flag.startsWith("--")) {
      throw new Error("expected paired path options");
    }
    if (values.has(flag)) {
      throw new Error(`duplicate option ${flag}`);
    }
    values.set(flag, value);
  }
  const required = ["--journal", "--config", "--output", "--cache-dir"];
  for (const flag of required) {
    if (!values.has(flag)) {
      throw new Error(`missing option ${flag}`);
    }
  }
  if (values.size !== required.length) {
    throw new Error("unknown option");
  }
  return {
    journal: values.get("--journal")!,
    config: values.get("--config")!,
    output: values.get("--output")!,
    cacheDir: values.get("--cache-dir")!,
  };
}

function encodePackage(value: ReplayPackage): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function main(): void {
  const args = parseArguments(process.argv.slice(2));
  fs.mkdirSync(path.dirname(args.output), { recursive: true });
  if (fs.existsSync(args.output)) {
    fs.unlinkSync(args.output);
  }

  const derived = deriveProvenance(args.journal, args.config);
  const cachePath = path.join(args.cacheDir, `${derived.cacheKey}.json`);
  if (fs.existsSync(cachePath)) {
    fs.copyFileSync(cachePath, args.output);
    return;
  }

  const bridge = process.env.G7_BRIDGE ?? "/app/environment/bin/g7bridge";
  const raw = execFileSync(bridge, ["replay", args.journal, args.config], { encoding: "utf8" });
  const pkg = JSON.parse(raw) as ReplayPackage;
  if (
    pkg.provenance.journal_digest !== derived.journalDigest ||
    pkg.provenance.config_digest !== derived.configDigest
  ) {
    throw new Error("cross-language provenance mismatch");
  }

  fs.mkdirSync(args.cacheDir, { recursive: true });
  const encoded = encodePackage(pkg);
  fs.writeFileSync(cachePath, encoded);
  fs.writeFileSync(args.output, encoded);
}

main();
