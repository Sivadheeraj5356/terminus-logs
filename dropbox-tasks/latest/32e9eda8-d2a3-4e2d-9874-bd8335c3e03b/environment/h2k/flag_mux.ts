export function fn_h2(seed: string, armTbl: Record<string, string>, gate: number): [number, Buffer] {
  void armTbl;
  const outs = ['lane.out'];
  if (gate) {
    outs.push('meta.bin');
  }
  const manifestBytes = Buffer.from(outs.join('|') + ':' + String(seed));
  return [1, manifestBytes];
}
