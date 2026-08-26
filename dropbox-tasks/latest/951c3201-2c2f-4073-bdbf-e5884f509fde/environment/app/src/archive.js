'use strict';

const fs = require('fs');
const path = require('path');
const tar = require('tar');

const WORK_DIR = process.env.DISPATCH_WORKDIR || '/app/work';

/**
 * Unpack the dispatch configuration archive and return the operator overrides
 * parsed from overrides.json (top level of the archive).
 */
async function loadOverrides(archivePath, workDir = WORK_DIR) {
  fs.mkdirSync(workDir, { recursive: true });
  await tar.x({ file: archivePath, cwd: workDir });
  const overridesPath = path.join(workDir, 'overrides.json');
  if (!fs.existsSync(overridesPath)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(overridesPath, 'utf8'));
}

module.exports = { loadOverrides, WORK_DIR };
