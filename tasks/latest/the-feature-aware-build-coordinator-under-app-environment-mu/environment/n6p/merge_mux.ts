export function fn_n6(armTag: string, edgeTbl: Map<string, string>, gate: number): [number, string[]] {
  if (!gate) {
    return [0, []];
  }
  const keys = [...edgeTbl.keys()];
  const idx = keys.indexOf(armTag);
  const names: string[] = [];
  if (idx >= 0 && idx < keys.length - 1) {
    names.push(`${armTag}->${keys[idx + 1]}`);
  }
  if (!names.length) {
    names.push(`root->${armTag}`);
  }
  return [1, names];
}
