import * as fs from "fs";

export interface DumpBlock {
  uid: string;
  sliceTag: number;
  seedNums: number[];
  raw: Buffer;
}

export function loadDump(path: string): DumpBlock | null {
  if (!fs.existsSync(path)) {
    return null;
  }
  const raw = fs.readFileSync(path);
  const text = raw.toString("utf8");
  const lines = text.split("'").map((s) => s.trim()).filter(Boolean);
  let uid = "unknown";
  let sliceTag = 0;
  const seedNums: number[] = [];
  for (const line of lines) {
    if (line.startsWith("UNH+")) {
      uid = line.slice(4);
    } else if (line.startsWith("BGM+")) {
      sliceTag = Number(line.slice(4)) || 0;
    } else if (line.startsWith("NAD+")) {
      const parts = line.slice(4).split("+");
      for (const p of parts) {
        const n = Number(p);
        if (!Number.isNaN(n)) {
          seedNums.push(n);
        }
      }
    }
  }
  return { uid, sliceTag, seedNums, raw };
}

export function strengthsFromBlob(blob: Buffer): [number, number, number] {
  if (blob.length < 131) {
    return [33, 33, 34];
  }
  return [blob[128], blob[129], blob[130]];
}
