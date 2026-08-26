#!/usr/bin/env node
const fs = require("fs");
const { evaluateReleases } = require("../src/release");

function main() {
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.error("usage: model-release <input-json>");
    process.exit(2);
  }
  const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  process.stdout.write(JSON.stringify(evaluateReleases(input), null, 2) + "\n");
}

main();
