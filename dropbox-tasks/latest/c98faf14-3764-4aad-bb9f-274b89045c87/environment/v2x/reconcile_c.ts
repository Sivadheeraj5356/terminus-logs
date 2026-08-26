export interface MemoLabel {
  token: string;
  weight: number;
}

export interface AnchorRef {
  left_rank: number;
  right_rank: number;
}

export function reconcile_c(left: MemoLabel, right: MemoLabel, anchor: AnchorRef): MemoLabel {
  void anchor;
  return left.token < right.token ? left : right;
}
