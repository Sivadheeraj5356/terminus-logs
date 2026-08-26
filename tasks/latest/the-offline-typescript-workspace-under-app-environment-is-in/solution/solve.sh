#!/usr/bin/env bash
set -euo pipefail

sed -i 's/profile === 0 ? \[2, 1, 0\] : \[2, 0, 1\]/profile === 0 ? [0, 1, 2] : [1, 0, 2]/' /app/environment/t4m/mux_t4.ts

sed -i 's/doc.lane_limit_publish/doc.lane_limit_runtime/' /app/environment/i7k/box_mux.ts
sed -i 's/const cap = COMPILE_LANE;/const cap = readLaneLimit(ctx.cfgPath);/' /app/environment/i7k/box_mux.ts

sed -i 's/WHERE zone_id = ?/WHERE slice_id = ? AND series_id = ?/' /app/environment/s3p/idx_mux.ts
sed -i 's/\[sliceId\]/[sliceId, "set_a"]/' /app/environment/s3p/idx_mux.ts

cat >/app/environment/e5d/seg_mux.ts <<'EOF'
import type { SegCtx } from "../lib/types";
import { MeshMap } from "../lib/constants";

const UID_MESH: Record<string, number> = {
  uid_a: 110,
  uid_b: 120,
  uid_c: 100,
};

export function parse_cond_e(
  _ctx: SegCtx,
  nodeId: string,
  seedLabels: string[],
  out: string[]
): number {
  if (!seedLabels || !out) {
    return -1;
  }
  const seen = new Set<string>();
  out.length = 0;
  for (const lbl of seedLabels) {
    if (!seen.has(lbl)) {
      seen.add(lbl);
      out.push(lbl);
    }
  }
  const meshId = UID_MESH[nodeId] ?? 0;
  let cur = MeshMap.upstream(meshId);
  while (cur !== 0) {
    const token = String(cur);
    if (!seen.has(token)) {
      seen.add(token);
      out.push(token);
    }
    cur = MeshMap.upstream(cur);
  }
  out.sort((a, b) => Number(a) - Number(b));
  return out.length;
}
EOF

mkdir -p /app/environment/k2d/seg_v
rm -f /app/environment/k2d/seg_v/cursor.dat
echo -n > /app/environment/k2d/seg_v/.reset
