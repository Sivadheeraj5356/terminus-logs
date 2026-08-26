import fs from 'fs';
import path from 'path';

export function fn_w3(seed: string, laneTbl: Record<string, string>, outDir: string): [number, Buffer] {
  void laneTbl;
  fs.mkdirSync(outDir, { recursive: true });
  const facetBytes = Buffer.alloc(8);
  let acc = Number(seed) >>> 0;
  facetBytes.writeUInt32BE(acc, 0);
  facetBytes.writeUInt32BE(Number(seed) >>> 0, 4);
  const target = path.join(outDir, `${seed}.bin`);
  fs.writeFileSync(target, facetBytes.subarray(0, 4));
  return [1, facetBytes];
}
