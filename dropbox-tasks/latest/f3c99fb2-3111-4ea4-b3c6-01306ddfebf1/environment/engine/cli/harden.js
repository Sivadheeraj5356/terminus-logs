#!/usr/bin/env node
'use strict';

const path = require('path');
const { hardenMediaInferenceDefaults } = require('../index');

const [repoRoot, dossierPath, fixtureDir, outDir] = process.argv.slice(2);
if (![repoRoot, dossierPath, fixtureDir, outDir].every(Boolean)) {
  console.error('usage: harden.js <repo-root> <dossier-path> <fixture-dir> <out-dir>');
  process.exitCode = 2;
} else {
  hardenMediaInferenceDefaults(path.resolve(repoRoot), path.resolve(dossierPath), path.resolve(fixtureDir), path.resolve(outDir))
    .catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });
}
