#!/usr/bin/env node
/** Immutable semver range probe used by grading immutability checks. */
import { readFileSync } from "node:fs";

const sample = process.argv[2] || "^1.2.3";
const version = process.argv[3] || "1.9.9";
const caret = (c, v) => {
  const m = c.match(/^\^(\d+)\.(\d+)\.(\d+)/);
  if (!m) return false;
  const major = Number(m[1]);
  const base = m.slice(1).map(Number);
  const parts = v.split(/[.+]/)[0].split(".").map(Number);
  if (parts[0] !== base[0]) return false;
  if (major > 0) return parts[0] === base[0];
  return parts[1] === base[1];
};
process.stdout.write(String(caret(sample, version)));
