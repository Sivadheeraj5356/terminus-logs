'use strict';

const fs = require('fs');
const path = require('path');

function readManifest(fixtureDir) {
  const manifest = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'manifest.json'), 'utf8'));
  if (!Array.isArray(manifest.fixtures) || !manifest.fixtures.length) throw new Error('manifest has no fixtures');
  return manifest.fixtures.slice().sort((left, right) => left.id.localeCompare(right.id));
}

module.exports = { readManifest };
