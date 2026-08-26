import { readFileSync } from "node:fs";

const HANDBOOK = "/app/docs/bastion_access_handbook.md";

function parseRules(text) {
  const rules = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("RULE:")) continue;
    const body = trimmed.slice("RULE:".length);
    const idx = body.indexOf("=");
    if (idx === -1) continue;
    rules[body.slice(0, idx)] = body.slice(idx + 1);
  }
  return rules;
}

function normalizeMode(mode) {
  const digits = String(mode).replace(/^0+/, "") || "0";
  return digits.padStart(4, "0");
}

/** Handbook-only last-wins RULE merge (ratified). */
export function loadPolicyRules() {
  return parseRules(readFileSync(HANDBOOK, "utf8"));
}

export function modeCompare(expected, actual, _rules) {
  return normalizeMode(expected) === normalizeMode(actual);
}

export function archiveStripPrefix(relativePath, _rules) {
  return relativePath;
}

export function handbookPath() {
  return HANDBOOK;
}
