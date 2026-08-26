#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { loadConfig, parseArgs } = require('./config');
const { simulate } = require('./simulator');
const { writeOutputs } = require('./output');

function main() {
  const { configPath, outDir } = parseArgs(process.argv.slice(2));
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });
  const config = loadConfig(configPath);
  const result = simulate(config);
  writeOutputs(config, result, outDir);
}

try {
  main();
} catch (error) {
  process.stderr.write(`thermal-cycle: ${error.message}\n`);
  process.exitCode = 1;
}
