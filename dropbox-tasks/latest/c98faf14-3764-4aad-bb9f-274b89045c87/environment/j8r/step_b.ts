export interface ScoreBlock {
  block_id: string;
  block_hash: string;
  lane: string;
}

export interface HoldLedger {
  tomb_ids: string[];
  prior: ScoreBlock[];
}

function uniqueById(blocks: ScoreBlock[]): ScoreBlock[] {
  const seen = new Set<string>();
  const out: ScoreBlock[] = [];
  for (const block of blocks) {
    if (seen.has(block.block_id)) continue;
    seen.add(block.block_id);
    out.push(block);
  }
  return out;
}

function mergePrior(fresh: ScoreBlock[], prior: ScoreBlock[]): ScoreBlock[] {
  const seen = new Set(fresh.map((b) => b.block_id));
  const out = [...fresh];
  for (const block of prior) {
    if (seen.has(block.block_id)) continue;
    out.push(block);
    seen.add(block.block_id);
  }
  return out;
}

export function step_b(blocks: ScoreBlock[], ledger: HoldLedger): ScoreBlock[] {
  const merged = mergePrior(blocks, ledger.prior);
  return uniqueById(merged);
}
