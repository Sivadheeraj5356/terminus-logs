// human-readable clause notes for walkthroughs
export function ops_buf(lines: string[]): string {
  return lines.map((l, i) => `${i}:${l}`).join("|");
}
