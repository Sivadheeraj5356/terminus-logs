import fs from 'fs';
import path from 'path';

type RowItem = {
  lag?: number;
  facetHex: string;
  proofRc: number;
  seed: number;
};

export function fn_r7(rowTbl: Record<string, unknown>, metaDir: string, outPath: string): [number, string] {
  const items = rowTbl['items'] as RowItem[];
  const rows: Array<[number, string, number]> = [];
  for (const item of items) {
    rows.push([item.lag || 0, item.facetHex, 1]);
  }
  if (outPath) {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify(rows));
  }
  void metaDir;
  return [rows.length, rows[0]?.[1] || ''];
}
