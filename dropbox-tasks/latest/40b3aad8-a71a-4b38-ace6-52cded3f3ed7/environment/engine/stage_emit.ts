import * as fs from "fs";
import * as path from "path";
import { enclose_ivk } from "../i7k/box_mux";
import { BASIS } from "../lib/constants";
import { rowSig } from "../lib/sig_util";
import type { BoxCtx, RowRec, YamlSink } from "../lib/types";
import type { FoldedRec } from "./stage_fold";

function expandBasis(folded: FoldedRec[]): RowRec[] {
  const out: RowRec[] = [];
  for (const src of folded) {
    const basis = BASIS[src.classCode] || 1;
    for (let b = 0; b < basis; b += 1) {
      out.push({
        instanceUid: `${src.instanceUid}#b${b}`,
        meshId: src.meshId,
        classCode: src.classCode,
        labels: [...src.labels].sort((a, b) => a - b),
        weights: [...src.weights],
        o8Score: src.o8Score,
        latticeLabel: src.latticeLabel,
      });
    }
  }
  return out;
}

export function buildAndEmit(
  boxCtx: BoxCtx,
  folded: FoldedRec[],
  emitBatch: Map<string, unknown>
): void {
  const expanded = expandBasis(folded);
  const sink: YamlSink = {
    recs: [],
    push(rec: RowRec) {
      this.recs.push(rec);
    },
  };
  enclose_ivk(boxCtx, expanded, expanded.length, sink);
  emitBatch.set("emitted", sink.recs);
  emitBatch.set("staged", expanded.slice(0, Math.min(3, expanded.length)));
}

export function writeStagePartial(recs: RowRec[]): void {
  const dir = path.join("/app/output/stage");
  fs.mkdirSync(dir, { recursive: true });
  const body = recs.map((r) => {
    const labels = JSON.stringify(r.labels);
    const weights = JSON.stringify(r.weights.map((w) => Number(w.toFixed(4))));
    return `  - instance_uid: ${r.instanceUid}\n    mesh_id: ${r.meshId}\n    class_code: ${r.classCode}\n    labels: ${labels}\n    weights: ${weights}`;
  });
  const yaml = `rows:\n${body.join("\n")}\n`;
  fs.writeFileSync(path.join(dir, "partial.yaml"), yaml, "utf8");
}

export function writeLogExcerpt(recs: RowRec[]): void {
  const dir = path.join("/app/output/logs");
  fs.mkdirSync(dir, { recursive: true });
  const lines = recs.slice(0, 2).map((r) => `${r.instanceUid} score=${r.o8Score}\n`);
  fs.writeFileSync(path.join(dir, "sample.txt"), lines.join(""), "utf8");
}

export function renderYaml(sliceId: number, profile: number, recs: RowRec[]): string {
  const body = recs.map((r) => {
    const labels = JSON.stringify(r.labels);
    const weights = JSON.stringify(r.weights.map((w) => Number(w.toFixed(4))));
    const sig = rowSig(r);
    return (
      `  - instance_uid: ${r.instanceUid}\n` +
      `    mesh_id: ${r.meshId}\n` +
      `    class_code: ${r.classCode}\n` +
      `    labels: ${labels}\n` +
      `    weights: ${weights}\n` +
      `    o8_score: ${r.o8Score}\n` +
      `    lattice_label: ${r.latticeLabel}\n` +
      `    row_digest: ${sig}`
    );
  });
  return `slice_id: ${sliceId}\nprofile: ${profile}\nrows:\n${body.join("\n")}\n`;
}
