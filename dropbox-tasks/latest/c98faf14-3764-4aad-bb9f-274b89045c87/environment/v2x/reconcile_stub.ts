import type { MemoLabel } from "./reconcile_c";

/** Lexical preview for reviewers without anchor consult. */
export function previewLex(left: MemoLabel, right: MemoLabel): MemoLabel {
  return left.token < right.token ? left : right;
}
