import { readFileSync } from "node:fs";
import { join } from "node:path";

const HANDBOOK = "/app/docs/bastion_access_handbook.md";
const DESK = "/app/docs/access_desk.md";

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

export function loadPolicyRules() {
  const desk = readFileSync(DESK, "utf8");
  const handbook = readFileSync(HANDBOOK, "utf8");
  const handbookRules = {};
  for (const line of handbook.split("\n")) {
    if (line.includes("circulation draft — superseded")) {
      break;
    }
    const trimmed = line.trim();
    if (!trimmed.startsWith("RULE:")) continue;
    const body = trimmed.slice("RULE:".length);
    const idx = body.indexOf("=");
    if (idx === -1) continue;
    handbookRules[body.slice(0, idx)] = body.slice(idx + 1);
  }
  const merged = { ...handbookRules, ...parseRules(desk) };
  return merged;
}

export function modeCompare(expected, actual, rules) {
  const strategy = rules.MODE_COMPARE ?? "octal_normalized";
  if (strategy === "string_exact") {
    return String(expected) === String(actual);
  }
  return normalizeMode(expected) === normalizeMode(actual);
}

export function archiveStripPrefix(relativePath, rules) {
  const strategy = rules.ARCHIVE_STRIP_PREFIX ?? "preserve_relative";
  if (strategy === "first_segment") {
    const parts = relativePath.split("/");
    parts.shift();
    return parts.join("/");
  }
  return relativePath;
}

function normalizeMode(mode) {
  const digits = String(mode).replace(/^0+/, "") || "0";
  return digits.padStart(4, "0");
}

export function handbookPath() {
  return HANDBOOK;
}
