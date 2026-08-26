import * as fs from "fs";
import * as path from "path";
import initSqlJs from "sql.js";
import { idxClose, idxNext, link_slice_s } from "../s3p/idx_mux";
import type { D9Cursor, SegCtx } from "../lib/types";
import { SLICE_ID } from "../lib/constants";

export async function openStore(dbPath: string): Promise<unknown> {
  const wasmDir = path.join(__dirname);
  const SQL = await initSqlJs({
    locateFile: (file) => path.join(wasmDir, file),
  });
  const file = fs.readFileSync(dbPath);
  return new SQL.Database(file);
}

export async function ingestSeries(
  dbPath: string,
  sliceId: number,
  segCtx: SegCtx,
  batch: Map<string, unknown>
): Promise<number> {
  const db = await openStore(dbPath);
  const cursor: D9Cursor = { stmt: null, ready: 0 };
  const rc = link_slice_s(db, sliceId, cursor);
  if (rc < 0) {
    return rc;
  }
  const recs: Record<string, unknown>[] = [];
  let row = idxNext(cursor);
  while (row) {
    recs.push(row);
    row = idxNext(cursor);
  }
  idxClose(cursor);
  batch.set("instances", recs);
  batch.set("segCtx", segCtx);
  (batch as unknown as { _db: unknown })._db = db;
  return recs.length;
}

export function attachDumpBytes(
  dumpDir: string,
  recs: Record<string, unknown>[]
): void {
  for (const rec of recs) {
    const uid = String(rec.instance_uid);
    const dumpPath = path.join(dumpDir, `${uid}.edi`);
    if (fs.existsSync(dumpPath)) {
      rec.dump_bytes = fs.readFileSync(dumpPath);
    }
  }
}

export { SLICE_ID };
