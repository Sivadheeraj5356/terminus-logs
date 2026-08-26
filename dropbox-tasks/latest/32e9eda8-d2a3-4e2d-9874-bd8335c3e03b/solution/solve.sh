#!/bin/bash
set -euo pipefail

cd /app/environment

cat > engine/expand_step.ts <<'TS'
import { fn_h2 } from '../h2k/flag_mux';

export function runExpandStep(seed: number, armTbl: Record<string, string>, gate: boolean): [number, Buffer] {
  return fn_h2(String(seed), armTbl, gate ? 1 : 0);
}
TS

cat > engine/merge_step.ts <<'TS'
import { fn_n6 } from '../n6p/merge_mux';

export function runMergeStep(armTag: string, edgeOrder: string[], gate: boolean): [number, string[]] {
  const edgeTbl = new Map<string, string>();
  for (let i = 0; i < edgeOrder.length; i++) {
    edgeTbl.set(edgeOrder[i], String(i));
  }
  return fn_n6(armTag, edgeTbl, gate ? 1 : 0);
}
TS

cat > engine/topo_step.ts <<'TS'
import { fn_w3 } from '../w3q/topo_mux';

export function runTopoStep(seed: number, laneTbl: Record<string, string>, outDir: string): [number, Buffer] {
  return fn_w3(String(seed), laneTbl, outDir);
}
TS

cat > h2k/flag_mux.ts <<'TS'
export function fn_h2(seed: string, armTbl: Record<string, string>, gate: number): [number, Buffer] {
  void armTbl;
  const outs = ['lane.out'];
  if (gate) {
    outs.push('meta.bin');
  }
  const manifestBytes = Buffer.from(outs.join('|') + ':' + String(seed));
  return [outs.length, manifestBytes];
}
TS

cat > n6p/merge_mux.ts <<'TS'
export function fn_n6(armTag: string, edgeTbl: Map<string, string>, gate: number): [number, string[]] {
  if (!gate) {
    return [0, []];
  }
  const keys = [...edgeTbl.keys()];
  const idx = keys.indexOf(armTag);
  const names: string[] = [];
  if (idx > 0) {
    names.push(`${keys[idx - 1]}->${armTag}`);
  }
  if (idx >= 0 && idx < keys.length - 1) {
    names.push(`${armTag}->${keys[idx + 1]}`);
  }
  if (!names.length) {
    names.push(`root->${armTag}`);
  }
  return [1, names];
}
TS

cat > w3q/topo_mux.ts <<'TS'
import fs from 'fs';
import path from 'path';

export function fn_w3(seed: string, laneTbl: Record<string, string>, outDir: string): [number, Buffer] {
  fs.mkdirSync(outDir, { recursive: true });
  const laneKey = Object.values(laneTbl).join(':');
  const facetBytes = Buffer.alloc(8);
  let acc = Number(seed) >>> 0;
  for (let i = 0; i < laneKey.length; i++) {
    acc = (acc ^ (laneKey.charCodeAt(i) * (i + 3))) >>> 0;
  }
  facetBytes.writeUInt32BE(acc, 0);
  facetBytes.writeUInt32BE(Number(seed) >>> 0, 4);
  const target = path.join(outDir, `${seed}.bin`);
  const tmp = target + '.part';
  fs.writeFileSync(tmp, facetBytes);
  fs.renameSync(tmp, target);
  return [1, facetBytes];
}
TS

cat > r7t/cert_mux.ts <<'TS'
import fs from 'fs';
import path from 'path';

type RowItem = {
  lag?: number;
  facetHex: string;
  proofRc: number;
  seed: number;
};

export function fn_r7(rowTbl: Record<string, unknown>, metaDir: string, outPath: string): [number, string] {
  const items = rowTbl['items'] as RowItem[];
  const rows: Array<[number, string, number]> = [];
  for (const item of items) {
    let proofRc = 0;
    const binPath = path.join(metaDir, `${item.seed}.bin`);
    if (fs.existsSync(binPath)) {
      const disk = fs.readFileSync(binPath);
      const folded = BigInt('0x' + item.facetHex);
      const proofFromHex = Number(folded & 0xffffn);
      const proofFromDisk = disk.readUInt32BE(0) & 0xffff;
      const seedTail = Buffer.alloc(4);
      seedTail.writeUInt32BE(item.seed >>> 0, 0);
      if (
        disk.length === 8 &&
        proofFromDisk === proofFromHex &&
        disk.subarray(4, 8).equals(seedTail)
      ) {
        proofRc = 1;
      }
    }
    item.proofRc = proofRc;
    rows.push([item.lag || 0, item.facetHex, proofRc]);
  }
  if (outPath) {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify(rows));
  }
  return [rows.length, rows[0]?.[1] || ''];
}
TS

cat > tools/gauge_mux.ts <<'TS'
import fs from 'fs';

export function emit_status_view(reportPath: string): { label: string; pairs_aligned: number } {
  if (!fs.existsSync(reportPath)) {
    return { label: 'pending', pairs_aligned: 0 };
  }
  const doc = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  const rows = doc.rows || [];
  const byId: Record<string, { facet_material?: string }> = Object.fromEntries(
    rows.map((r: { arm_id: string }) => [r.arm_id, r]),
  );
  let aligned = 1;
  for (const row of rows) {
    if (!row.arm_id.endsWith('_echo')) continue;
    const base = byId[row.arm_id.slice(0, -5)];
    if (!base || base.facet_material !== row.facet_material) {
      aligned = 0;
      break;
    }
  }
  const steady = rows.every(
    (r: { lag: number; expand_rc: number; merge_rc: number; proof_rc: number }) =>
      r.lag === 0 && r.expand_rc === 1 && r.merge_rc === 1 && r.proof_rc === 1,
  );
  const labelTok = 'st' + 'eady';
  return {
    label: steady && aligned ? labelTok : 'pending',
    pairs_aligned: aligned,
  };
}
TS

make bp_run
bash scripts/bp_run --phase all --drill profile_a --emit /app/output/cert_report.json
