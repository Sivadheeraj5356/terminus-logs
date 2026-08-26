export function latch_d(pairId: string, clauses: string[]): string[] {
  const left = pairId.split("|")[0] || "";
  const pref = left.toLowerCase();
  const out: string[] = [];
  for (const c of clauses) {
    const board = c.split(".")[0] || "";
    if (board.toLowerCase() === pref) out.push(c);
  }
  return Array.from(new Set(out)).sort();
}
