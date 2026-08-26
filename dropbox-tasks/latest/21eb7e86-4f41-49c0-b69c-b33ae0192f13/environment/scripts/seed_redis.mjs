#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const fixturesDir = process.env.REDIS_FIXTURES_DIR ?? "/app/redis_fixtures";
const redisPort = process.env.REDIS_PORT ?? "6379";
const manifest = JSON.parse(
  readFileSync(join(fixturesDir, "seed_manifest.json"), "utf8"),
);

function load(name) {
  return readFileSync(join(fixturesDir, name), "utf8");
}

function redisCmd(args) {
  const proc = spawnSync("redis-cli", ["-p", redisPort, ...args], {
    encoding: "utf8",
  });
  if (proc.status !== 0) {
    throw new Error(`redis-cli failed: ${proc.stderr}`);
  }
  return proc.stdout.trim();
}

function hset(key, jsonObj) {
  for (const [field, value] of Object.entries(jsonObj)) {
    const payload = typeof value === "string" ? value : JSON.stringify(value);
    redisCmd(["HSET", key, field, payload]);
  }
}

const tenants = [
  "prod",
  "staging",
  "canary",
  "dr",
  "edge",
  "vault",
  "atlas",
  "comet",
  "orbit",
  "pulse",
  "nexus",
  "rift",
  "prism",
  "quasar",
  "aurora",
  "helix",
  "vertex",
  "continuum",
  "eclipse",
  "nebula",
  "solstice",
  "pulsar",
  "zenith",
  "lumen",
  "cobalt",
  "vector",
  "horizon",
  "flux",
  "apex",
  "relay",
  "spire",
  "nova",
  "titan",
  "forge",
  "ember",
  "onyx",
  "sentinel",
  "cipher",
  "quartz",
  "obsidian",
  "garnet",
  "slate",
  "crimson",
  "jade",
  "opal",
  "ivory",
];

redisCmd(["FLUSHDB"]);
hset(manifest.keys.users, JSON.parse(load("users.json")));
hset(manifest.keys.ssh_keys, JSON.parse(load("ssh_keys.json")));
for (const member of JSON.parse(load("service_accounts.json"))) {
  redisCmd(["SADD", manifest.keys.service_accounts, member]);
}
hset(manifest.keys.file_modes, JSON.parse(load("file_modes.json")));
hset(manifest.keys.sshd_settings, JSON.parse(load("sshd_settings.json")));
hset(manifest.keys.sudoers_lines, JSON.parse(load("sudoers_lines.json")));
for (const tenant of tenants) {
  hset(
    manifest.keys.tenant_overlay.replace("{tenant}", tenant),
    JSON.parse(load(`tenant_${tenant}.json`)),
  );
  hset(
    `bastion:registry:cache:${tenant}`,
    JSON.parse(load(`registry_cache_${tenant}.json`)),
  );
}
