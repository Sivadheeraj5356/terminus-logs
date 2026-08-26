import * as fs from "fs";
import * as path from "path";
import { attachDumpBytes, ingestSeries, SLICE_ID } from "../engine/stage_ingest";
import { foldBatch } from "../engine/stage_fold";
import {
  buildAndEmit,
  renderYaml,
  writeLogExcerpt,
  writeStagePartial,
} from "../engine/stage_emit";
import { bumpCursor, cursorValue } from "../engine/seg_store";
import type { BoxCtx, SegCtx, TraceCtx } from "../lib/types";

function parseArgs(argv: string[]): Record<string, string> {
  let dumpDir = "/app/environment/fixtures/set_a";
  let idxStore = "/app/environment/data/idx_store.db";
  let out = "/app/output/inv_d9.yaml";
  let i = 0;
  while (i < argv.length) {
    if (argv[i] === "--dump-dir" && i + 1 < argv.length) {
      dumpDir = argv[i + 1];
      i += 2;
    } else if (argv[i] === "--idx-store" && i + 1 < argv.length) {
      idxStore = argv[i + 1];
      i += 2;
    } else if (argv[i] === "--out" && i + 1 < argv.length) {
      out = argv[i + 1];
      i += 2;
    } else {
      i += 1;
    }
  }
  return { "dump-dir": dumpDir, "idx-store": idxStore, out };
}

async function main(): Promise<void> {
  const opts = parseArgs(process.argv.slice(2));
  const batch = new Map<string, unknown>();
  const segCtx: SegCtx = { foldUpstream: true };
  const traceCtx: TraceCtx = { profile: 0 };
  const boxCtx: BoxCtx = { cfgPath: "/app/environment/data/cfg_d9.yaml" };

  const rc = await ingestSeries(opts["idx-store"], SLICE_ID, segCtx, batch);
  if (rc < 0) {
    process.exit(3);
  }
  const instances = batch.get("instances") as Record<string, unknown>[];
  attachDumpBytes(opts["dump-dir"], instances);
  for (const rec of instances) {
    const uid = String(rec.instance_uid);
    const dumpPath = path.join(opts["dump-dir"], `${uid}.edi`);
    const tagPath = path.join(opts["dump-dir"], `${uid}.tag`);
    if (fs.existsSync(tagPath)) {
      rec.tag_blob = fs.readFileSync(tagPath);
    } else {
      const { loadDump } = await import("../p759/fmt_parse");
      const block = loadDump(dumpPath);
      if (block) {
        rec.tag_blob = block.raw;
      }
    }
  }

  const folded = foldBatch(traceCtx, segCtx, instances);
  const emitBatch = new Map<string, unknown>();
  buildAndEmit(boxCtx, folded, emitBatch);

  const staged = emitBatch.get("staged") as import("../lib/types").RowRec[];
  const emitted = emitBatch.get("emitted") as import("../lib/types").RowRec[];
  writeStagePartial(staged);
  writeLogExcerpt(emitted);
  bumpCursor();

  const outPath = opts.out;
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const yaml = renderYaml(SLICE_ID, 0, emitted);
  fs.writeFileSync(outPath, yaml, "utf8");

  if (cursorValue() < 0) {
    process.exit(4);
  }
  process.exit(0);
}

main().catch((err) => {
  console.error(String(err));
  process.exit(5);
});
