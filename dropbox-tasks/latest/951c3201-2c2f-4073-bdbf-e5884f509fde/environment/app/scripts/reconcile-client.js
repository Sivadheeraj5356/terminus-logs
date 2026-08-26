'use strict';

const fs = require('fs');
const path = require('path');

const { loadConfig } = require('../src/config');
const { loadCanonicalZones } = require('../src/canonical');
const { loadOverrides } = require('../src/archive');
const { computeTarget, FIELDS } = require('../src/reconcile');

const cfg = loadConfig();
const BASE_URL = `http://127.0.0.1:${cfg.http.port}`;

// Deterministic JSON: object keys are emitted in sorted order so the report is
// byte-for-byte stable across runs.
function stableStringify(value) {
  if (Array.isArray(value)) {
    return '[' + value.map(stableStringify).join(',') + ']';
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map((k) => JSON.stringify(k) + ':' + stableStringify(value[k])).join(',') + '}';
  }
  return JSON.stringify(value);
}

async function getZones() {
  const res = await fetch(`${BASE_URL}/zones`);
  if (!res.ok) throw new Error(`GET /zones failed: ${res.status}`);
  return res.json();
}

async function putZone(id, target) {
  const res = await fetch(`${BASE_URL}/zones/${id}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(target),
  });
  if (!res.ok) throw new Error(`PUT /zones/${id} failed: ${res.status}`);
  return res.json();
}

async function main() {
  const canonical = loadCanonicalZones(cfg.canonicalCsv);
  const overrides = await loadOverrides(cfg.overridesArchive);
  const zones = await getZones();

  const changes = [];
  let reconciled = 0;
  let unchanged = 0;
  let lockedOverrides = 0;
  let unknown = 0;

  for (const zone of zones) {
    const id = zone.location_id;
    const current = { borough: zone.borough, zone: zone.zone, service_zone: zone.service_zone };
    const canonRow = canonical.get(id) || null;
    const override = overrides[String(id)];

    const { target, appliedLockedOverride, known } = computeTarget(current, canonRow, override);

    if (!known) {
      unknown += 1;
      continue;
    }
    if (appliedLockedOverride) lockedOverrides += 1;

    const changedFields = FIELDS.filter((f) => target[f] !== current[f]).sort();
    if (changedFields.length > 0) {
      await putZone(id, target);
      const reason = appliedLockedOverride ? 'override_locked' : 'reconciled';
      if (reason === 'reconciled') reconciled += 1;
      changes.push({ location_id: id, fields: changedFields, reason });
    } else {
      unchanged += 1;
    }
  }

  changes.sort((a, b) => a.location_id - b.location_id);

  const report = {
    generated_from: 'redis',
    total_zones: zones.length,
    reconciled,
    unchanged,
    locked_overrides: lockedOverrides,
    unknown_zones: unknown,
    changes,
  };

  fs.mkdirSync(path.dirname(cfg.reportPath), { recursive: true });
  fs.writeFileSync(cfg.reportPath, stableStringify(report) + '\n');
  process.stdout.write(`reconciled=${reconciled} unchanged=${unchanged} locked=${lockedOverrides} unknown=${unknown}\n`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
