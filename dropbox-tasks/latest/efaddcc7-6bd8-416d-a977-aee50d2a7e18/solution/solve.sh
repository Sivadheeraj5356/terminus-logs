#!/bin/bash
set -euo pipefail

cat > /app/environment/q9/k4_fold.ts <<'EOF'
import * as crypto from "crypto";

function toHex8(value: number): string {
  let hex = (value >>> 0).toString(16);
  while (hex.length < 8) {
    hex = "0" + hex;
  }
  return hex;
}

function sortSlots(slots: Uint32Array): number[] {
  const values: number[] = [];
  for (let i = 0; i < slots.length; i++) {
    values.push(slots[i] >>> 0);
  }
  values.sort((a, b) => a - b);
  return values;
}

function buildPayload(sorted: number[], salt: number): string {
  const parts: string[] = [];
  for (const value of sorted) {
    parts.push(toHex8(value));
  }
  return parts.join(":") + "#" + salt.toString(16);
}

function hashPrefix(payload: string): string {
  return crypto.createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}

export function foldK4(slots: Uint32Array, salt: number): string {
  const saltU = salt >>> 0;
  if (slots.length === 0) {
    return hashPrefix("#" + saltU.toString(16));
  }
  const sorted = sortSlots(slots);
  const payload = buildPayload(sorted, saltU);
  return hashPrefix(payload);
}
EOF

cat > /app/environment/w2/n8_mix.ts <<'EOF'
const MOD = 1000003;

function sortedCopy(cells: number[]): number[] {
  const out = cells.slice();
  out.sort((a, b) => a - b);
  return out;
}

function stepMix(acc: number, cell: number, weight: number): number {
  const next = acc + cell * weight;
  return ((next % MOD) + MOD) % MOD;
}

function normalizeWeight(weight: number): number {
  if (!Number.isFinite(weight)) {
    return 0;
  }
  return weight | 0;
}

export function mixN8(prior: number, cells: number[], weight: number): number {
  let acc = prior | 0;
  const w = normalizeWeight(weight);
  const ordered = sortedCopy(cells);
  for (let i = 0; i < ordered.length; i++) {
    acc = stepMix(acc, ordered[i] | 0, w);
  }
  return acc;
}
EOF

cat > /app/environment/v7/p3_knit.ts <<'EOF'
import * as crypto from "crypto";

function sortedCells(cells: number[]): number[] {
  const out = cells.slice();
  out.sort((a, b) => a - b);
  return out;
}

function buildBindPayload(digest: string, epoch: number, cells: number[]): string {
  const ordered = sortedCells(cells);
  return digest + "|" + String(epoch >>> 0) + "|" + ordered.join(",");
}

function hashPrefix(payload: string): string {
  return crypto.createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}

export function knitP3(digest: string, epoch: number, cells: number[]): string {
  const safeDigest = typeof digest === "string" ? digest : "";
  const payload = buildBindPayload(safeDigest, epoch, cells);
  return hashPrefix(payload);
}
EOF

cd /app/environment
npm run build
mkdir -p /app/output
npm run play -- --cases /app/environment/fixtures/cases.toml
