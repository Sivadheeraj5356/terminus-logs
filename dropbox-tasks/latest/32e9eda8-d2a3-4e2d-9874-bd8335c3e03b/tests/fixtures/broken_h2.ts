export function fn_h2(seed: string, armTbl: Record<string, string>, gate: number): [number, Buffer] {
  void armTbl;
  void gate;
  const outs = ['lane.out'];
  const manifestBytes = Buffer.from(outs.join('|') + ':broken:' + String(seed) + '\x00');
  return [outs.length, manifestBytes];
}
