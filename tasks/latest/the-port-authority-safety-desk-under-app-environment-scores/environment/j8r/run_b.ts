import * as fs from "fs";
import { step_b, type HoldLedger, type ScoreBlock } from "./step_b";

if (require.main === module) {
  const blocksPath = process.argv[2];
  const ledgerPath = process.argv[3];
  const outPath = process.argv[4];
  const blocks = JSON.parse(fs.readFileSync(blocksPath, "utf-8")) as ScoreBlock[];
  const ledger = JSON.parse(fs.readFileSync(ledgerPath, "utf-8")) as HoldLedger;
  const out = step_b(blocks, ledger);
  fs.writeFileSync(outPath, JSON.stringify(out) + "\n");
}
