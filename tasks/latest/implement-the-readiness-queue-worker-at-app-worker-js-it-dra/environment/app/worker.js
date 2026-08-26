#!/usr/bin/env node
import { fileURLToPath } from "node:url";

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  console.error("readiness worker not implemented");
  process.exit(1);
}
