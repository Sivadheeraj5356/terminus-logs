import * as fs from "fs";
import * as path from "path";

const SEG_DIR = path.join("/app/environment/k2d/seg_v");
const CURSOR = path.join(SEG_DIR, "cursor.dat");

export function bumpCursor(): void {
  fs.mkdirSync(SEG_DIR, { recursive: true });
  let val = 0;
  if (fs.existsSync(CURSOR)) {
    val = Number(fs.readFileSync(CURSOR, "utf8")) || 0;
  }
  fs.writeFileSync(CURSOR, String(val + 1), "utf8");
}

export function cursorValue(): number {
  if (!fs.existsSync(CURSOR)) {
    return 0;
  }
  return Number(fs.readFileSync(CURSOR, "utf8")) || 0;
}
