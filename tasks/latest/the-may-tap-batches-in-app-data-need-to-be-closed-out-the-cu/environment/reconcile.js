#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const outputDir = "/app/output";

function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  throw new Error("fare closeout not implemented");
}

main();
