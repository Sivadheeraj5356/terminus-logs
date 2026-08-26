import { fn_r7 } from '../r7t/cert_mux';

type ArmState = {
  aid: string;
  facetHex: string;
  expandRc: number;
  mergeRc: number;
  proofRc: number;
  lag: number;
  seed: number;
};

export function materializeRows(arms: ArmState[], metaDir: string) {
  const rowTbl = {
    items: arms.map((a) => ({
      aid: a.aid,
      facetHex: a.facetHex,
      lag: a.lag,
      expandRc: a.expandRc,
      mergeRc: a.mergeRc,
      proofRc: a.proofRc,
      seed: a.seed,
    })),
  };
  fn_r7(rowTbl, metaDir, '');
  return rowTbl.items.map((r) => ({
    arm_id: r.aid,
    facet_material: r.facetHex,
    expand_rc: r.expandRc,
    merge_rc: r.mergeRc,
    proof_rc: r.proofRc,
    lag: r.lag,
  }));
}
