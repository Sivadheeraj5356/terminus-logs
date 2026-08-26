const MOD = 1000003;

function sortedCopy(cells: number[]): number[] {
  const out = cells.slice();
  out.sort((a, b) => a - b);
  return out;
}

function stepMix(acc: number, cell: number, weight: number): number {
  const next = acc + cell * weight;
  return ((next % MOD) + MOD) % MOD;
}

function normalizeWeight(weight: number): number {
  if (!Number.isFinite(weight)) {
    return 0;
  }
  return weight | 0;
}

export function mixN8(prior: number, cells: number[], weight: number): number {
  let acc = prior | 0;
  const w = normalizeWeight(weight);
  const ordered = sortedCopy(cells);
  for (let i = 0; i < ordered.length; i++) {
    acc = stepMix(acc, ordered[i] | 0, w);
  }
  return acc;
}
