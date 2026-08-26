import fs from 'fs';
import path from 'path';

export function fn_w3(seed: string, laneTbl: Record<string, string>, outDir: string): [number, Buffer] {
  fs.mkdirSync(outDir, { recursive: true });
  const laneKey = Object.values(laneTbl).join(':');
  const facetBytes = Buffer.alloc(8);
  let acc = Number(seed) >>> 0;
  for (let i = 0; i < laneKey.length; i++) {
    acc = (acc ^ (laneKey.charCodeAt(i) * (i + 2))) >>> 0;
  }
  facetBytes.writeUInt32BE(acc, 0);
  facetBytes.writeUInt32BE(Number(seed) >>> 0, 4);
  const target = path.join(outDir, `${seed}.bin`);
  fs.writeFileSync(target, facetBytes);
  return [1, facetBytes];
}
