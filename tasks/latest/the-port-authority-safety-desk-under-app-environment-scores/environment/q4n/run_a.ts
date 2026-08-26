import * as fs from "fs";
import { op_a, type RotRow } from "./phase_a";

if (require.main === module) {
  const inPath = process.argv[2];
  const floor = Number(process.argv[3]);
  const outPath = process.argv[4];
  const rows = JSON.parse(fs.readFileSync(inPath, "utf-8")) as RotRow[];
  const slice = op_a(rows, floor);
  fs.writeFileSync(outPath, JSON.stringify(slice) + "\n");
}
