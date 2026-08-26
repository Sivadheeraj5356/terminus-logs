import type { SegCtx } from "../lib/types";

export function parse_cond_e(
  _ctx: SegCtx,
  _nodeId: string,
  seedLabels: string[],
  out: string[]
): number {
  if (!seedLabels || !out) {
    return -1;
  }
  out.length = 0;
  for (const lbl of seedLabels) {
    out.push(lbl);
  }
  return out.length;
}
