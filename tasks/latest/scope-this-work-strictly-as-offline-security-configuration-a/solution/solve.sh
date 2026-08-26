#!/usr/bin/env bash
set -euo pipefail

cat > /workspace/streamvault/src/harden.mjs <<'EOF'
#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const POLICY_DATE = "2025-12-31";

function runTool(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
    ...options,
  });
  if (result.error || result.status !== 0) {
    const detail = result.stderr?.trim() || result.error?.message || `exit ${result.status}`;
    throw new Error(`${command} failed: ${detail}`);
  }
  return result.stdout;
}

function parseArgs(argv) {
  if (argv.length % 2 !== 0) throw new Error("arguments must be --name value pairs");
  const parsed = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i].startsWith("--")) throw new Error(`invalid argument: ${argv[i]}`);
    parsed[argv[i].slice(2)] = argv[i + 1];
  }
  for (const name of ["fleet-db", "runbook", "input", "output"]) {
    if (!parsed[name]) throw new Error(`missing --${name}`);
  }
  return parsed;
}

function query(db, sql) {
  const text = runTool("sqlite3", ["-readonly", "-json", db, sql]).trim();
  if (!text) return [];
  const rows = JSON.parse(text);
  if (!Array.isArray(rows)) throw new Error("sqlite3 returned a non-array result");
  return rows;
}

function canonicalJson(value) {
  return runTool("jq", ["-S", "."], { input: JSON.stringify(value) }).replace(/\n*$/, "\n");
}

function canonicalKey(value) {
  return canonicalJson(value).trim();
}

function sha256FromOutput(output) {
  const digest = output.trim().split(/\s+/)[0];
  if (!/^[0-9a-f]{64}$/.test(digest)) throw new Error("sha256sum returned an invalid digest");
  return digest;
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function ensureObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value;
}

function ipv4Number(value, label) {
  if (typeof value !== "string" || !/^\d+\.\d+\.\d+\.\d+$/.test(value)) {
    throw new Error(`${label} must be a dotted-quad IPv4 address`);
  }
  const octets = value.split(".").map(Number);
  if (octets.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    throw new Error(`${label} contains an invalid IPv4 octet`);
  }
  return octets.reduce((number, part) => number * 256 + part, 0);
}

function cidrContains(address, cidr) {
  if (typeof cidr !== "string") throw new Error("allowed_cidr must be a string");
  const pieces = cidr.split("/");
  if (pieces.length !== 2 || !/^\d+$/.test(pieces[1])) throw new Error(`invalid CIDR: ${cidr}`);
  const prefix = Number(pieces[1]);
  if (prefix < 0 || prefix > 32) throw new Error(`invalid CIDR prefix: ${cidr}`);
  const candidate = BigInt(ipv4Number(address, "service exception address"));
  const network = BigInt(ipv4Number(pieces[0], "CIDR network"));
  const mask = prefix === 0 ? 0n : (0xffffffffn << BigInt(32 - prefix)) & 0xffffffffn;
  return (candidate & mask) === (network & mask);
}

function parseInputs(inputDir) {
  const yamlPath = path.join(inputDir, "streamvault.yaml");
  const servicesPath = path.join(inputDir, "services.json");
  if (!fs.statSync(yamlPath).isFile() || !fs.statSync(servicesPath).isFile()) {
    throw new Error("required input files must be regular files");
  }
  const configText = runTool("yq", ["-o=json", ".", yamlPath]);
  const servicesText = runTool("jq", ["-S", ".", servicesPath]);
  return {
    config: ensureObject(JSON.parse(configText), "streamvault.yaml"),
    services: ensureObject(JSON.parse(servicesText), "services.json"),
  };
}

function siteEvidence(site) {
  return { source: "sqlite:sites", key: "site_id", value: site.site_id };
}

function runbookEvidence(controlId) {
  return { source: "runbook", rationale_id: controlId };
}

function sortEvidence(evidence) {
  return evidence.sort((left, right) => canonicalKey(left).localeCompare(canonicalKey(right)));
}

function resolveException(controlId, candidates, supersessions) {
  if (candidates.length === 0) return undefined;
  if (candidates.length === 1) return candidates[0];

  const byRationale = new Map(candidates.map((row) => [row.rationale_id, row]));
  if (byRationale.size !== candidates.length) {
    throw new Error(`ambiguous exceptions for ${controlId}: duplicate rationale`);
  }
  const outgoing = new Map([...byRationale.keys()].map((rationale) => [rationale, new Set()]));
  for (const edge of supersessions) {
    if (edge.control_id !== controlId) continue;
    if (!byRationale.has(edge.predecessor_rationale_id) || !byRationale.has(edge.successor_rationale_id)) continue;
    outgoing.get(edge.predecessor_rationale_id).add(edge.successor_rationale_id);
  }

  const state = new Map();
  function visit(rationale) {
    if (state.get(rationale) === "visiting") {
      throw new Error(`ambiguous exceptions for ${controlId}: supersession cycle`);
    }
    if (state.get(rationale) === "visited") return;
    state.set(rationale, "visiting");
    for (const successor of outgoing.get(rationale)) visit(successor);
    state.set(rationale, "visited");
  }
  for (const rationale of byRationale.keys()) visit(rationale);

  const terminals = [...outgoing.entries()]
    .filter(([, successors]) => successors.size === 0)
    .map(([rationale]) => rationale);
  if (terminals.length !== 1) {
    throw new Error(`ambiguous exceptions for ${controlId}: expected one terminal decision`);
  }
  const terminal = terminals[0];
  function reachesTerminal(start, seen = new Set()) {
    if (start === terminal) return true;
    if (seen.has(start)) return false;
    seen.add(start);
    return [...outgoing.get(start)].some((successor) => reachesTerminal(successor, new Set(seen)));
  }
  if ([...byRationale.keys()].some((rationale) => !reachesTerminal(rationale))) {
    throw new Error(`ambiguous exceptions for ${controlId}: disconnected decisions`);
  }
  return byRationale.get(terminal);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  for (const file of [args["fleet-db"], args.runbook]) {
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) throw new Error(`missing input: ${file}`);
  }

  const runbook = fs.readFileSync(args.runbook, "utf8");
  const rationales = new Set(
    [...runbook.matchAll(/^### Rationale: ([A-Za-z0-9_-]+)\s*$/gm)].map((match) => match[1]),
  );
  const controls = [
    "SV-IDENTITY-01",
    "SV-CREDENTIAL-02",
    "SV-AUTH-03",
    "SV-TLS-04",
    "SV-BIND-05",
    "SV-INGEST-06",
    "SV-SERVICE-07",
    "SV-RETENTION-08",
  ];
  for (const control of controls) {
    if (!runbook.includes(`### Control: ${control}`)) throw new Error(`runbook lacks ${control}`);
  }

  const { config, services } = parseInputs(args.input);
  const siteId = config.site_id;
  if (typeof siteId !== "string" || !siteId) throw new Error("site_id is required");
  ensureObject(config.security, "security");
  ensureObject(config.network, "network");
  ensureObject(config.recording, "recording");
  ensureObject(services.services, "services.services");

  const sites = query(args["fleet-db"], "SELECT site_id, admin_user, approved_bind, profile FROM sites ORDER BY site_id");
  const matches = sites.filter((row) => row.site_id === siteId);
  if (matches.length !== 1) throw new Error(`expected one site row for ${siteId}`);
  const site = matches[0];
  const cameras = query(args["fleet-db"], "SELECT camera_id, site_id, enabled, approved_port, media_fixture FROM cameras ORDER BY camera_id")
    .filter((row) => row.site_id === siteId);
  const policies = query(args["fleet-db"], "SELECT profile, min_days, max_days FROM retention_policies ORDER BY profile")
    .filter((row) => row.profile === site.profile);
  if (policies.length !== 1) throw new Error(`expected one retention policy for ${site.profile}`);
  const retentionPolicy = policies[0];
  const minDays = Number(retentionPolicy.min_days);
  const maxDays = Number(retentionPolicy.max_days);
  if (!Number.isInteger(minDays) || !Number.isInteger(maxDays) || minDays < 1 || maxDays > 365 || minDays > maxDays) {
    throw new Error(`invalid retention policy bounds for ${site.profile}`);
  }
  const serviceNetworks = query(args["fleet-db"], "SELECT profile, service_name, allowed_cidr FROM service_networks ORDER BY profile, service_name, allowed_cidr")
    .filter((row) => row.profile === site.profile);
  const exceptionRows = query(args["fleet-db"], "SELECT site_id, control_id, approved_value, rationale_id, expires_on FROM exceptions ORDER BY control_id, rationale_id")
    .filter((row) => row.site_id === siteId);
  const supersessionRows = query(args["fleet-db"], "SELECT site_id, control_id, predecessor_rationale_id, successor_rationale_id FROM exception_supersessions ORDER BY control_id, predecessor_rationale_id, successor_rationale_id")
    .filter((row) => row.site_id === siteId);

  const candidates = new Map();
  const warnings = [];
  for (const row of exceptionRows) {
    if (row.expires_on < POLICY_DATE) {
      warnings.push(`ignored expired exception ${row.rationale_id} for ${row.control_id}`);
      continue;
    }
    if (!rationales.has(row.rationale_id)) {
      warnings.push(`ignored unauthorized exception ${row.rationale_id} for ${row.control_id}`);
      continue;
    }
    if (!["SV-SERVICE-07", "SV-RETENTION-08"].includes(row.control_id)) continue;
    if (!candidates.has(row.control_id)) candidates.set(row.control_id, []);
    candidates.get(row.control_id).push(row);
  }
  const currentExceptions = new Map();
  for (const controlId of ["SV-SERVICE-07", "SV-RETENTION-08"]) {
    const selected = resolveException(controlId, candidates.get(controlId) ?? [], supersessionRows);
    if (selected) currentExceptions.set(controlId, selected);
  }

  const outputConfig = clone(config);
  const outputServices = clone(services);
  const changes = [];
  function addChange(controlId, fieldPath, before, after, evidence) {
    changes.push({
      control_id: controlId,
      path: fieldPath,
      before,
      after,
      evidence: sortEvidence(evidence),
    });
  }
  const base = (controlId) => [siteEvidence(site), runbookEvidence(controlId)];

  addChange("SV-IDENTITY-01", "security.admin_user", config.security.admin_user ?? null, site.admin_user, base("SV-IDENTITY-01"));
  outputConfig.security.admin_user = site.admin_user;

  addChange(
    "SV-CREDENTIAL-02",
    "security.admin_password",
    hasOwn(config.security, "admin_password") ? "[REDACTED]" : null,
    null,
    base("SV-CREDENTIAL-02"),
  );
  delete outputConfig.security.admin_password;
  addChange(
    "SV-CREDENTIAL-02",
    "security.admin_password_env",
    config.security.admin_password_env ?? null,
    "STREAMVAULT_ADMIN_PASSWORD",
    base("SV-CREDENTIAL-02"),
  );
  outputConfig.security.admin_password_env = "STREAMVAULT_ADMIN_PASSWORD";

  addChange("SV-AUTH-03", "security.allow_anonymous", config.security.allow_anonymous ?? null, false, base("SV-AUTH-03"));
  outputConfig.security.allow_anonymous = false;
  addChange("SV-TLS-04", "security.tls_required", config.security.tls_required ?? null, true, base("SV-TLS-04"));
  outputConfig.security.tls_required = true;
  addChange("SV-BIND-05", "network.bind", config.network.bind ?? null, site.approved_bind, base("SV-BIND-05"));
  outputConfig.network.bind = site.approved_bind;

  const mediaDir = path.resolve(args.input, "media");
  const eligible = [];
  for (const camera of cameras) {
    if (Number(camera.enabled) !== 1) {
      warnings.push(`ignored disabled camera ${camera.camera_id}`);
      continue;
    }
    const fixture = camera.media_fixture;
    if (typeof fixture !== "string" || path.basename(fixture) !== fixture) {
      warnings.push(`ignored unsafe media fixture for camera ${camera.camera_id}: ${String(fixture)}`);
      continue;
    }
    const mediaPath = path.resolve(mediaDir, fixture);
    let regular = false;
    try {
      regular = mediaPath.startsWith(`${mediaDir}${path.sep}`) && fs.lstatSync(mediaPath).isFile();
    } catch {
      regular = false;
    }
    if (!regular) {
      let existsButUnsafe = false;
      try {
        existsButUnsafe = fs.lstatSync(mediaPath).isSymbolicLink() || fs.existsSync(mediaPath);
      } catch {
        existsButUnsafe = false;
      }
      warnings.push(
        existsButUnsafe
          ? `ignored unsafe media fixture for camera ${camera.camera_id}: ${fixture}`
          : `ignored missing media fixture for camera ${camera.camera_id}: ${fixture}`,
      );
      continue;
    }
    const port = Number(camera.approved_port);
    if (!Number.isInteger(port) || port < 1024 || port > 65535) {
      throw new Error(`approved port out of range for camera ${camera.camera_id}`);
    }
    eligible.push({ ...camera, approved_port: port });
  }
  eligible.sort((a, b) => a.approved_port - b.approved_port || a.camera_id.localeCompare(b.camera_id));
  const ports = [...new Set(eligible.map((camera) => camera.approved_port))];
  const cameraEvidence = eligible.flatMap((camera) => [
    { source: "sqlite:cameras", key: "camera_id", value: camera.camera_id },
    { source: "media", filename: camera.media_fixture },
  ]);
  addChange("SV-INGEST-06", "network.ingest_ports", config.network.ingest_ports ?? null, ports, [...base("SV-INGEST-06"), ...cameraEvidence]);
  outputConfig.network.ingest_ports = ports;

  const ingestService = outputServices.services["camera-ingest"];
  if (!ingestService || typeof ingestService !== "object" || Array.isArray(ingestService)) {
    throw new Error("services.json lacks camera-ingest service");
  }
  const exposedPorts = ports.map((port) => `127.0.0.1:${port}:${port}/tcp`);
  addChange("SV-INGEST-06", "services.camera-ingest.ports", services.services["camera-ingest"].ports ?? null, exposedPorts, [...base("SV-INGEST-06"), ...cameraEvidence]);
  ingestService.ports = exposedPorts;

  let approvedBindings = {};
  const serviceException = currentExceptions.get("SV-SERVICE-07");
  if (serviceException) {
    approvedBindings = ensureObject(JSON.parse(serviceException.approved_value), "exception approved_value");
    for (const [name, bind] of Object.entries(approvedBindings)) {
      if (typeof bind !== "string" || !bind) throw new Error(`invalid service bind exception for ${name}`);
    }
  }
  const serviceNames = Object.keys(outputServices.services).sort();
  for (const name of Object.keys(approvedBindings).sort()) {
    if (!hasOwn(outputServices.services, name)) warnings.push(`ignored exception service not present in input: ${name}`);
  }
  const networkEvidence = new Map();
  for (const [name, address] of Object.entries(approvedBindings)) {
    if (!hasOwn(outputServices.services, name)) continue;
    ipv4Number(address, `service exception for ${name}`);
    const candidates = serviceNetworks.filter((row) => row.service_name === name);
    if (candidates.length === 0) throw new Error(`missing service network policy for ${name}`);
    const matches = candidates.filter((row) => cidrContains(address, row.allowed_cidr));
    if (matches.length === 0) throw new Error(`service exception for ${name} is outside approved networks`);
    networkEvidence.set(
      name,
      matches.map((row) => ({
        source: "sqlite:service_networks",
        key: "allowed_cidr",
        value: row.allowed_cidr,
      })),
    );
  }
  for (const name of serviceNames) {
    const service = ensureObject(outputServices.services[name], `service ${name}`);
    const after = typeof approvedBindings[name] === "string" ? approvedBindings[name] : "127.0.0.1";
    const evidence = base("SV-SERVICE-07");
    if (hasOwn(approvedBindings, name)) {
      evidence.push(
        { source: "sqlite:exceptions", key: "control_id", value: "SV-SERVICE-07" },
        { source: "runbook", rationale_id: serviceException.rationale_id },
        ...networkEvidence.get(name),
      );
    }
    addChange("SV-SERVICE-07", `services.${name}.bind`, service.bind ?? null, after, evidence);
    service.bind = after;
  }

  const beforeRetention = config.recording.retention_days;
  if (!Number.isInteger(beforeRetention)) throw new Error("recording.retention_days must be an integer");
  let afterRetention = Math.max(minDays, Math.min(maxDays, beforeRetention));
  const retentionEvidence = [
    ...base("SV-RETENTION-08"),
    { source: "sqlite:retention_policies", key: "profile", value: site.profile },
  ];
  const retentionException = currentExceptions.get("SV-RETENTION-08");
  if (retentionException) {
    const approvedDays = JSON.parse(retentionException.approved_value);
    if (!Number.isInteger(approvedDays) || approvedDays < 1 || approvedDays > 365) {
      throw new Error("invalid retention exception approved_value");
    }
    afterRetention = approvedDays;
    retentionEvidence.push(
      { source: "sqlite:exceptions", key: "control_id", value: "SV-RETENTION-08" },
      { source: "runbook", rationale_id: retentionException.rationale_id },
    );
  }
  addChange(
    "SV-RETENTION-08",
    "recording.retention_days",
    beforeRetention,
    afterRetention,
    retentionEvidence,
  );
  outputConfig.recording.retention_days = afterRetention;

  changes.sort((a, b) => a.control_id.localeCompare(b.control_id) || a.path.localeCompare(b.path));
  warnings.sort();
  const report = { policy_date: POLICY_DATE, site_id: siteId, changes, warnings };

  const output = path.resolve(args.output);
  const parent = path.dirname(output);
  fs.mkdirSync(parent, { recursive: true });
  const staging = fs.mkdtempSync(path.join(parent, `.${path.basename(output)}.staging-`));
  try {
    const configJson = canonicalJson(outputConfig);
    let yaml = runTool("yq", ["-P", "."], { input: configJson });
    yaml = yaml.replace(/^---\s*\n/, "").replace(/\n*$/, "\n");
    fs.writeFileSync(path.join(staging, "streamvault.yaml"), yaml, "utf8");
    fs.writeFileSync(path.join(staging, "services.json"), canonicalJson(outputServices), "utf8");
    fs.writeFileSync(path.join(staging, "hardening-report.json"), canonicalJson(report), "utf8");
    const artifactNames = ["hardening-report.json", "services.json", "streamvault.yaml"];
    const manifestFiles = artifactNames.map((name) => ({
      path: name,
      sha256: sha256FromOutput(runTool("sha256sum", [path.join(staging, name)])),
    }));
    const rootInput = manifestFiles.map((entry) => `${entry.sha256}  ${entry.path}\n`).join("");
    const manifest = {
      algorithm: "sha256",
      files: manifestFiles,
      root_sha256: sha256FromOutput(runTool("sha256sum", [], { input: rootInput })),
    };
    fs.writeFileSync(path.join(staging, "bundle-manifest.json"), canonicalJson(manifest), "utf8");
    fs.rmSync(output, { recursive: true, force: true });
    fs.renameSync(staging, output);
  } catch (error) {
    fs.rmSync(staging, { recursive: true, force: true });
    throw error;
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`streamvault-hardener: ${error.message}\n`);
  process.exitCode = 1;
}
EOF

chmod +x /workspace/streamvault/src/harden.mjs
