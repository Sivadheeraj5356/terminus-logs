import * as fs from "fs/promises";

export async function readDossier(path: string): Promise<string> {
  return fs.readFile(path, "utf8");
}

export function findSection(dossier: string, heading: RegExp): string | null {
  const lines = dossier.split("\n");
  let start = -1;
  let depth = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (start === -1) {
      if (heading.test(line)) {
        const match = line.match(/^(#{1,6})\s/);
        depth = match ? match[1].length : 1;
        start = i + 1;
      }
    } else {
      const nextHeading = line.match(/^(#{1,6})\s/);
      if (nextHeading && nextHeading[1].length <= depth) {
        return lines.slice(start, i).join("\n");
      }
    }
  }
  if (start !== -1) return lines.slice(start).join("\n");
  return null;
}

export function extractPaths(text: string): string[] {
  const matches = text.match(/\/[a-zA-Z0-9_\-./]+/g) ?? [];
  return [...new Set(matches.filter((p) => p.length > 2))];
}
