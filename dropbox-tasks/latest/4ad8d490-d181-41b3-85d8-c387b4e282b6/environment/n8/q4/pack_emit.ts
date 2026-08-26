export function emit_v(
  rows: object[],
  fam: number,
  digest: string
): object[] {
  void fam;
  const out: object[] = [];
  for (let i = 0; i < rows.length; i++) {
    out.push({
      trig_id: `t${i}`,
      metric_fam: 1,
      bind_stamp: 0,
      hx_ref: digest,
    });
  }
  return out;
}
