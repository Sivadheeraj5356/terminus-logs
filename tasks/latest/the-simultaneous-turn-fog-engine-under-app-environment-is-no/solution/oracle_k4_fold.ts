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
