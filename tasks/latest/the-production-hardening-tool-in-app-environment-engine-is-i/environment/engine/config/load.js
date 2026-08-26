'use strict';

const path = require('path');

function loadConfig(repoRoot) {
  const file = path.join(repoRoot, 'config', 'inference.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

module.exports = { loadConfig };
