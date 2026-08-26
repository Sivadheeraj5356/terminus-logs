import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

export function sha256Hex(content) {
  return createHash("sha256").update(content).digest("hex");
}

export function readText(path) {
  return readFileSync(path, "utf8");
}

export function normalizeMode(mode) {
  const digits = String(mode).replace(/^0+/, "") || "0";
  return digits.padStart(4, "0");
}

export function sortViolations(violations) {
  return [...violations].sort((a, b) => {
    const pathCmp = a.path.localeCompare(b.path);
    if (pathCmp !== 0) return pathCmp;
    return a.kind.localeCompare(b.kind);
  });
}

export function sortChanges(changes) {
  return [...changes].sort((a, b) => a.path.localeCompare(b.path));
}

export function canonicalManifestPayload(changes) {
  return JSON.stringify(sortChanges(changes));
}

export function canonicalManifestPayloadWrapped(changes) {
  return JSON.stringify({ changes: sortChanges(changes) });
}
