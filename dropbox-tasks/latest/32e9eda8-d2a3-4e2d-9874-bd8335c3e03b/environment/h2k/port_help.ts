export function formatPortTable(rows: Array<{ tag: string; slot: number }>): string {
  return rows.map((r) => `${r.tag}:${r.slot}`).join(',');
}
