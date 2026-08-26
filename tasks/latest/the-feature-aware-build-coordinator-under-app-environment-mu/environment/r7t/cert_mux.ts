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
    let proofRc = item.proofRc;
    const binPath = path.join(metaDir, `${item.seed}.bin`);
    if (fs.existsSync(binPath)) {
      const disk = fs.readFileSync(binPath);
      const folded = BigInt('0x' + item.facetHex);
      const proofFromHex = Number(folded & 0xffffn);
      const proofFromDisk = disk.readUInt32BE(0) & 0xff;
      if (disk.length === 8 && proofFromDisk === (proofFromHex & 0xff)) {
        proofRc = 1;
      }
    }
    rows.push([item.lag || 0, item.facetHex, proofRc]);
  }
  if (outPath) {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify(rows));
  }
  return [rows.length, rows[0]?.[1] || ''];
}
