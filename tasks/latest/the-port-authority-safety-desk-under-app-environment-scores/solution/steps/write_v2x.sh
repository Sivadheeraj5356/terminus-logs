#!/bin/bash
set -euo pipefail

cd /app/environment

cat > v2x/reconcile_c.ts <<'EOF'
export interface MemoLabel {
  token: string;
  weight: number;
}

export interface AnchorRef {
  left_rank: number;
  right_rank: number;
}

function pickByWeight(left: MemoLabel, right: MemoLabel): MemoLabel {
  if (left.weight === right.weight) {
    return left.token <= right.token ? left : right;
  }
  return left.weight > right.weight ? left : right;
}

function pickByAnchor(left: MemoLabel, right: MemoLabel, anchor: AnchorRef): MemoLabel {
  if (anchor.left_rank < anchor.right_rank) {
    return left;
  }
  if (anchor.right_rank < anchor.left_rank) {
    return right;
  }
  return pickByWeight(left, right);
}

export function reconcile_c(left: MemoLabel, right: MemoLabel, anchor: AnchorRef): MemoLabel {
  return pickByAnchor(left, right, anchor);
}
EOF
