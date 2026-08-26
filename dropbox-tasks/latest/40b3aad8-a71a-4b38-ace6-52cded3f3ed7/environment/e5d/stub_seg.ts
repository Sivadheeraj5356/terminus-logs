import type { SegCtx } from "../lib/types";

export function stub_seg(_ctx: SegCtx, seedLabels: string[]): string[] {
  return [...seedLabels];
}
