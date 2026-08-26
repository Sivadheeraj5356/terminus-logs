#!/bin/bash
set -euo pipefail

cd /app/environment

cat > j8r/step_b.ts <<'EOF'
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

function dropTombstones(blocks: ScoreBlock[], tomb: Set<string>): ScoreBlock[] {
  const out: ScoreBlock[] = [];
  for (const block of blocks) {
    if (tomb.has(block.block_id)) continue;
    out.push(block);
  }
  return out;
}

function mergePrior(fresh: ScoreBlock[], prior: ScoreBlock[], tomb: Set<string>): ScoreBlock[] {
  const seen = new Set(fresh.map((b) => b.block_id));
  const out = [...fresh];
  for (const block of prior) {
    if (tomb.has(block.block_id)) continue;
    if (seen.has(block.block_id)) continue;
    out.push(block);
    seen.add(block.block_id);
  }
  return out;
}

export function step_b(blocks: ScoreBlock[], ledger: HoldLedger): ScoreBlock[] {
  const tomb = new Set(ledger.tomb_ids);
  const filtered = dropTombstones(blocks, tomb);
  const merged = mergePrior(filtered, ledger.prior, tomb);
  return uniqueById(merged);
}
EOF
