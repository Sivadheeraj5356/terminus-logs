import { createHash } from "crypto";
import type { RowRec } from "./types";

export function rowSig(rec: RowRec): string {
  const labelCsv = [...rec.labels].sort((a, b) => a - b).join(",");
  const weightCsv = rec.weights.map((w) => w.toFixed(4)).join(",");
  const canon = `${rec.instanceUid}|${labelCsv}|${weightCsv}`;
  return createHash("sha256").update(canon).digest("hex");
}

export function labelRank(id: number): number {
  return (id % 7) + 1;
}

export function o8Score(seed: number[], folded: number[]): number {
  const seedSum = seed.reduce((acc, v) => acc + labelRank(v), 0);
  const foldSum = folded.reduce((acc, v) => acc + labelRank(v), 0);
  return foldSum - seedSum;
}
