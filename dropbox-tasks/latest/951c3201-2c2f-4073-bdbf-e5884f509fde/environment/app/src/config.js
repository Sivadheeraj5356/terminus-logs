'use strict';

const fs = require('fs');

const CONFIG_JSON = process.env.DISPATCH_CONFIG || '/app/config/service.json';
const CONFIG_ENV = process.env.DISPATCH_CONFIG_ENV || '/app/config/service.overrides';

// Configuration is layered: service.json holds the base values, and any matching
// key in service.overrides wins over it (the override file takes precedence over
// the JSON base, the usual 12-factor precedence). Operators use the override
// file to pin per-host connection details without editing the shared JSON.
const ENV_KEYS = {
  DISPATCH_REDIS_URL: ['redis', 'url'],
  DISPATCH_HTTP_PORT: ['http', 'port'],
  DISPATCH_CANONICAL_CSV: ['canonicalCsv'],
  DISPATCH_OVERRIDES_ARCHIVE: ['overridesArchive'],
  DISPATCH_REPORT_PATH: ['reportPath'],
};

function parseEnvFile(text) {
  const out = {};
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function setPath(obj, pathArr, value) {
  let node = obj;
  for (let i = 0; i < pathArr.length - 1; i += 1) {
    if (typeof node[pathArr[i]] !== 'object' || node[pathArr[i]] === null) {
      node[pathArr[i]] = {};
    }
    node = node[pathArr[i]];
  }
  node[pathArr[pathArr.length - 1]] = value;
}

function loadConfig() {
  const cfg = JSON.parse(fs.readFileSync(CONFIG_JSON, 'utf8'));
  if (fs.existsSync(CONFIG_ENV)) {
    const env = parseEnvFile(fs.readFileSync(CONFIG_ENV, 'utf8'));
    for (const [key, target] of Object.entries(ENV_KEYS)) {
      if (env[key] !== undefined && env[key] !== '') {
        let value = env[key];
        if (target.length === 2 && target[0] === 'http' && target[1] === 'port') {
          value = Number.parseInt(value, 10);
        }
        setPath(cfg, target, value);
      }
    }
  }
  return cfg;
}

module.exports = { loadConfig };
