import { fn_n6 } from '../n6p/merge_mux';

export function runMergeStep(armTag: string, edgeOrder: string[], gate: boolean): [number, string[]] {
  const edgeTbl = new Map<string, string>();
  for (let i = 0; i < edgeOrder.length; i++) {
    edgeTbl.set(edgeOrder[i], String(i));
  }
  return fn_n6(armTag, edgeTbl, gate ? 0 : 1);
}
