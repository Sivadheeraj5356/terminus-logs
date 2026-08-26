'use strict';

const fs = require('fs');
const path = require('path');

const repoRoot = '/app/environment/engine';
function put(relative, content) {
  fs.writeFileSync(path.join(repoRoot, relative), content.trimStart(), 'utf8');
}

put('lib/dossier/effective.js', String.raw`
'use strict';

const REQUIRED = ['security', 'sre'];
const FIELDS = ['debugInferenceEnabled', 'corsAllowedOrigins', 'maxUploadBytes', 'telemetryRedactionEnabled', 'telemetryRedactedFields', 'moderationThresholds'];

function hasApprovals(record, names) { return names.every((name) => record.approvals.includes(name)); }
function parseBoolean(value) { if (value === 'true') return true; if (value === 'false') return false; throw new Error('invalid boolean decision'); }
function parseList(value) { const result = value.split(',').map((item) => item.trim()).filter(Boolean); if (!result.length) throw new Error('empty list decision'); return result; }
function parseThresholds(value) {
  const result = {};
  for (const item of value.split(',')) {
    const [label, raw] = item.split('=').map((part) => part.trim());
    const number = Number(raw);
    if (!['safe', 'suggestive', 'explicit'].includes(label) || !Number.isFinite(number) || number < 0 || number > 1) throw new Error('invalid threshold decision');
    result[label] = number;
  }
  if (Object.keys(result).length !== 3) throw new Error('incomplete threshold decision');
  return result;
}
function values(delta) {
  const out = {};
  if (delta.debugInferenceEnabled !== undefined) out.debugInferenceEnabled = parseBoolean(delta.debugInferenceEnabled);
  if (delta.corsAllowedOrigins !== undefined) out.corsAllowedOrigins = parseList(delta.corsAllowedOrigins);
  if (delta.maxUploadBytes !== undefined) { const value = Number(delta.maxUploadBytes); if (!Number.isInteger(value) || value <= 0) throw new Error('invalid upload decision'); out.maxUploadBytes = value; }
  if (delta.telemetryRedactionEnabled !== undefined) out.telemetryRedactionEnabled = parseBoolean(delta.telemetryRedactionEnabled);
  if (delta.telemetryRedactedFields !== undefined) out.telemetryRedactedFields = parseList(delta.telemetryRedactedFields);
  if (delta.moderationThresholds !== undefined) out.moderationThresholds = parseThresholds(delta.moderationThresholds);
  return out;
}
function resolveEffectivePolicy(records) {
  const eligible = records.filter((record) => record.scope === 'production' && record.state === 'ratified' && hasApprovals(record, REQUIRED));
  const byId = new Map(records.map((record) => [record.id, record]));
  const replaced = new Map();
  for (const record of eligible) for (const id of record.supersedes) replaced.set(id, record);
  const selected = {};
  for (const record of eligible.sort((a, b) => a.recordedAt.localeCompare(b.recordedAt))) {
    const changed = values(record.delta);
    for (const [field, value] of Object.entries(changed)) {
      if ((field === 'telemetryRedactionEnabled' || field === 'telemetryRedactedFields') && !hasApprovals(record, ['privacy'])) continue;
      const predecessor = byId.get(record.id);
      const superseder = replaced.get(predecessor.id);
      if (superseder && values(superseder.delta)[field] !== undefined) continue;
      if (selected[field] !== undefined) throw new Error('dossier has conflicting active production decisions');
      selected[field] = value;
    }
  }
  if (FIELDS.some((field) => selected[field] === undefined)) throw new Error('dossier does not resolve a unique ratified production policy');
  return selected;
}

module.exports = { resolveEffectivePolicy };
`);

put('lib/fixtures/manifest.js', String.raw`
'use strict';
const fs = require('fs');
const path = require('path');
function readManifest(directory) {
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'manifest.json'), 'utf8'));
  if (!Array.isArray(manifest.fixtures) || !manifest.fixtures.length) throw new Error('manifest has no fixtures');
  const ids = new Set(); const indexes = new Set();
  for (const fixture of manifest.fixtures) {
    if (!fixture || typeof fixture.id !== 'string' || !Number.isInteger(fixture.index) || typeof fixture.file !== 'string') throw new Error('invalid fixture manifest entry');
    if (ids.has(fixture.id) || indexes.has(fixture.index)) throw new Error('duplicate fixture manifest entry');
    ids.add(fixture.id); indexes.add(fixture.index);
  }
  return manifest.fixtures.slice().sort((left, right) => left.index - right.index);
}
module.exports = { readManifest };
`);

put('lib/rewrite/config.js', String.raw`
'use strict';
function renderConfig(policy, current) {
  const next = {
    ...current,
    debugInferenceEnabled: policy.debugInferenceEnabled,
    cors: { ...current.cors, origin: policy.corsAllowedOrigins },
    corsAllowedOrigins: policy.corsAllowedOrigins,
    maxUploadBytes: policy.maxUploadBytes,
    telemetryRedactionEnabled: policy.telemetryRedactionEnabled,
    telemetryRedactedFields: policy.telemetryRedactedFields,
    telemetry: { ...current.telemetry, redactionEnabled: policy.telemetryRedactionEnabled },
    moderationThresholds: policy.moderationThresholds,
  };
  return "'use strict';\n\nconst inferenceConfig = " + JSON.stringify(next, null, 2) + ";\n\nmodule.exports = inferenceConfig;\n";
}
module.exports = { renderConfig };
`);

put('lib/rewrite/tfvars.js', String.raw`
'use strict';
function literal(value) { return Array.isArray(value) ? '[' + value.map((item) => JSON.stringify(item)).join(', ') + ']' : String(value); }
function update(text, key, value) {
  const expression = new RegExp('^\\s*' + key + '\\s*=.*$', 'gm');
  const matches = text.match(expression) || [];
  if (matches.length !== 1) throw new Error('expected exactly one assignment for ' + key);
  return text.replace(expression, key + ' = ' + literal(value));
}
function renderTfvars(policy, original) {
  let text = original;
  for (const [key, value] of Object.entries({
    debug_inference_enabled: policy.debugInferenceEnabled,
    cors_allowed_origins: policy.corsAllowedOrigins,
    max_upload_bytes: policy.maxUploadBytes,
    telemetry_redaction_enabled: policy.telemetryRedactionEnabled,
    telemetry_redacted_fields: policy.telemetryRedactedFields,
    moderation_threshold_safe: policy.moderationThresholds.safe,
    moderation_threshold_suggestive: policy.moderationThresholds.suggestive,
    moderation_threshold_explicit: policy.moderationThresholds.explicit,
  })) text = update(text, key, value);
  return text.endsWith('\n') ? text : text + '\n';
}
module.exports = { renderTfvars };
`);

put('lib/rewrite/transaction.js', String.raw`
'use strict';
const fs = require('fs');
const path = require('path');
function writeTransaction(writes) {
  const staged = [];
  const backups = [];
  try {
    for (const { file, content } of writes) {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      const temp = path.join(path.dirname(file), '.' + path.basename(file) + '.' + process.pid + '.next');
      fs.writeFileSync(temp, content, 'utf8');
      staged.push({ file, temp });
    }
    for (const { file, temp } of staged) {
      const backup = file + '.' + process.pid + '.prior';
      if (fs.existsSync(file)) { fs.renameSync(file, backup); backups.push({ file, backup }); }
      fs.renameSync(temp, file);
    }
    for (const { backup } of backups) fs.unlinkSync(backup);
  } catch (error) {
    for (const { temp } of staged) if (fs.existsSync(temp)) fs.unlinkSync(temp);
    for (const { file, backup } of backups.reverse()) { if (fs.existsSync(file)) fs.unlinkSync(file); if (fs.existsSync(backup)) fs.renameSync(backup, file); }
    throw error;
  }
}
module.exports = { writeTransaction };
`);

put('lib/artifacts/write.js', String.raw`
'use strict';
const path = require('path');
function json(value) { return JSON.stringify(value, null, 2) + '\n'; }
function outputWrites(outDir, policy, terraform, decisions) {
  return [
    { file: path.join(outDir, 'deployment-policy.json'), content: json(policy) },
    { file: path.join(outDir, 'terraform-defaults.json'), content: json(terraform) },
    { file: path.join(outDir, 'fixture-decisions.json'), content: json({ decisions }) },
  ];
}
module.exports = { outputWrites };
`);

put('index.js', String.raw`
'use strict';
const fs = require('fs');
const path = require('path');
const { parseRecords } = require('./lib/dossier/records');
const { resolveEffectivePolicy } = require('./lib/dossier/effective');
const { readManifest } = require('./lib/fixtures/manifest');
const { evaluateFixtures } = require('./lib/fixtures/evaluate');
const { renderConfig } = require('./lib/rewrite/config');
const { renderTfvars } = require('./lib/rewrite/tfvars');
const { writeTransaction } = require('./lib/rewrite/transaction');
const { terraformDefaults } = require('./lib/artifacts/schema');
const { outputWrites } = require('./lib/artifacts/write');
const { loadConfig } = require('./config/load');
async function hardenMediaInferenceDefaults(repoRoot, dossierPath, fixtureDir, outDir) {
  const policy = resolveEffectivePolicy(parseRecords(fs.readFileSync(dossierPath, 'utf8')));
  const current = loadConfig(repoRoot);
  const fixtures = readManifest(fixtureDir);
  const decisions = await evaluateFixtures(fixtures, fixtureDir, policy, repoRoot);
  const tfvarsPath = path.join(repoRoot, 'terraform', 'production.tfvars');
  const tfvars = fs.readFileSync(tfvarsPath, 'utf8');
  writeTransaction([
    { file: path.join(repoRoot, 'config', 'inference.js'), content: renderConfig(policy, current) },
    { file: tfvarsPath, content: renderTfvars(policy, tfvars) },
    ...outputWrites(outDir, policy, terraformDefaults(policy), decisions),
  ]);
  return policy;
}
module.exports = { hardenMediaInferenceDefaults };
`);
