import * as fs from "fs";
import { reconcile_c, type AnchorRef, type MemoLabel } from "./reconcile_c";

if (require.main === module) {
  const left = JSON.parse(process.argv[2]) as MemoLabel;
  const right = JSON.parse(process.argv[3]) as MemoLabel;
  const anchor = JSON.parse(process.argv[4]) as AnchorRef;
  const outPath = process.argv[5];
  const winner = reconcile_c(left, right, anchor);
  fs.writeFileSync(outPath, JSON.stringify(winner) + "\n");
}
