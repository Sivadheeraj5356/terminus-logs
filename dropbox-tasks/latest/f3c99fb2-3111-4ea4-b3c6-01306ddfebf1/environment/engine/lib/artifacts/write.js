'use strict';

const path = require('path');
function json(value) { return `${JSON.stringify(value, null, 2)}\n`; }
function outputWrites(outDir, policy, terraform, decisions) {
  return [
    { file: path.join(outDir, 'deployment-policy.json'), content: json(policy) },
    { file: path.join(outDir, 'terraform-defaults.json'), content: json(terraform) },
    { file: path.join(outDir, 'fixture-decisions.json'), content: json({ decisions }) },
  ];
}
module.exports = { outputWrites };
