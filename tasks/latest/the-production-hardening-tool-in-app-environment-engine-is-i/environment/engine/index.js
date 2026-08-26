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

async function hardenMediaInferenceDefaults(repoRoot, dossierPath, fixtureDir, outDir) {
  const records = parseRecords(fs.readFileSync(dossierPath, 'utf8'));
  const policy = resolveEffectivePolicy(records);
  const currentConfig = require(path.join(repoRoot, 'config', 'inference.js'));
  const fixtures = readManifest(fixtureDir);
  const decisions = await evaluateFixtures(fixtures, fixtureDir, policy, repoRoot);
  writeTransaction([
    { file: path.join(repoRoot, 'config', 'inference.js'), content: renderConfig(policy, currentConfig.service) },
    { file: path.join(repoRoot, 'terraform', 'production.tfvars'), content: renderTfvars(policy) },
    ...outputWrites(outDir, policy, terraformDefaults(policy), decisions),
  ]);
  return policy;
}

module.exports = { hardenMediaInferenceDefaults };
