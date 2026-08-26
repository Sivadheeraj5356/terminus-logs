// filename scan helper for docs examples
export function frag_scan(names: string[]): string[] {
  return names.filter((n) => n.endsWith(".json")).sort();
}
