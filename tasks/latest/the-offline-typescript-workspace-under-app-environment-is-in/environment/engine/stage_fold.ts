import { parse_cond_e } from "../e5d/seg_mux";
import { pick_mux_m } from "../t4m/mux_t4";
import { strengthsFromBlob } from "../p759/fmt_parse";
import { MeshMap } from "../lib/constants";
import { o8Score } from "../lib/sig_util";
import type { SegCtx, TraceCtx } from "../lib/types";

export interface FoldedRec {
  instanceUid: string;
  meshId: number;
  classCode: number;
  seedNums: number[];
  labels: number[];
  weights: number[];
  latticeLabel: string;
  o8Score: number;
}

export function foldBatch(
  traceCtx: TraceCtx,
  segCtx: SegCtx,
  instances: Record<string, unknown>[]
): FoldedRec[] {
  const out: FoldedRec[] = [];
  for (const rec of instances) {
    const uid = String(rec.instance_uid);
    const meshId = Number(rec.mesh_id);
    const classCode = Number(rec.class_code);
    const seedText = String(rec.seed_labels || "");
    const seedNums = seedText
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => !Number.isNaN(n));
    const blob = rec.tag_blob as Buffer | Uint8Array;
    const buf = Buffer.isBuffer(blob) ? blob : Buffer.from(blob);
    const strengths = strengthsFromBlob(buf);
    const arm = new Float64Array(strengths);
    const lblBuf: string[] = ["", "", ""];
    const dom = pick_mux_m(traceCtx, arm, 3, lblBuf);
    const seedStr = seedNums.map((n) => String(n));
    const foldedStr: string[] = [];
    parse_cond_e(segCtx, uid, seedStr, foldedStr);
    const labels = foldedStr.map((s) => Number(s)).filter((n) => !Number.isNaN(n));
    const weights = Array.from(arm.slice(0, 3));
    const latticeLabel = lblBuf[dom] || `L${traceCtx.profile}${dom}`;
    const score = o8Score(seedNums, labels);
    out.push({
      instanceUid: uid,
      meshId,
      classCode,
      seedNums,
      labels,
      weights,
      latticeLabel,
      o8Score: score,
    });
    void MeshMap.upstream(meshId);
  }
  return out;
}
