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
