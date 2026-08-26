export function formatLaneTable(tags: string[]): string {
  return tags.map((t, i) => `${i}:${t}`).join(' ');
}
