#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function fail(message) {
  process.stderr.write(`streamvault-hardener: ${message}\n`);
  process.exitCode = 1;
}

function runTool(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
    ...options,
  });
  if (result.error || result.status !== 0) {
    throw new Error(`${command} failed: ${result.stderr || result.error?.message}`);
  }
  return result.stdout;
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index];
    const value = argv[index + 1];
    if (!name?.startsWith("--") || value === undefined) {
      throw new Error("expected --fleet-db, --runbook, --input, and --output");
    }
    args[name.slice(2)] = value;
  }
  for (const name of ["fleet-db", "runbook", "input", "output"]) {
    if (!args[name]) throw new Error(`missing --${name}`);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const yamlPath = path.join(args.input, "streamvault.yaml");
  const servicesPath = path.join(args.input, "services.json");

  // The command-line tools are part of the task contract. Keep these probes: the
  // implementation must use their output rather than replacing them in JavaScript.
  runTool("sqlite3", ["-version"]);
  runTool("jq", ["--version"]);
  runTool("yq", ["--version"]);

  if (!fs.existsSync(yamlPath) || !fs.existsSync(servicesPath)) {
    throw new Error("required StreamVault input files are missing");
  }

  // TODO: query fleet.db, reconcile the YAML and JSON through yq/jq, validate
  // the runbook rationales and media fixtures, then atomically emit all outputs.
  throw new Error("hardening planner is not implemented");
}

main().catch((error) => fail(error.message));
