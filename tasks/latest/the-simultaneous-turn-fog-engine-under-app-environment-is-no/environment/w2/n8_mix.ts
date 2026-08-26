export function mixN8(prior: number, cells: number[], weight: number): number {
  let acc = prior;
  const ordered = cells.slice().sort((a, b) => b - a);
  const bumped = weight + 1;
  for (const cell of ordered) {
    acc = (acc + cell * bumped) % 1000003;
  }
  return acc;
}
