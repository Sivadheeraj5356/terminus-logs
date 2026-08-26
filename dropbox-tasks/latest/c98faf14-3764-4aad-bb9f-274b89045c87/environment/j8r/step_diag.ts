import type { ScoreBlock } from "./step_b";

/** Counts unique block ids without invalidation semantics. */
export function tallyBlocks(blocks: ScoreBlock[]): number {
  return new Set(blocks.map((b) => b.block_id)).size;
}
