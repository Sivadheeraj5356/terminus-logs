import type { Database, D9Cursor } from "../lib/types";

type SqlHandle = {
  prepare: (sql: string) => {
    bind: (args: unknown[]) => void;
    step: () => boolean;
    getAsObject: () => Record<string, unknown>;
    free: () => void;
  };
};

function readRows(db: Database, sql: string, args: unknown[]): Record<string, unknown>[] {
  const handle = db as SqlHandle;
  const stmt = handle.prepare(sql);
  stmt.bind(args);
  const batch: Record<string, unknown>[] = [];
  while (stmt.step()) {
    batch.push(stmt.getAsObject());
  }
  stmt.free();
  return batch;
}

export function link_slice_s(
  db: Database,
  sliceId: number,
  cursor: D9Cursor
): number {
  if (!db || !cursor) {
    return -1;
  }
  const batch = readRows(
    db,
    "SELECT instance_uid, mesh_id, class_code, series_id, seed_labels, tag_blob FROM series_rows WHERE zone_id = ? ORDER BY instance_uid",
    [sliceId]
  );
  (cursor as unknown as { batch: Record<string, unknown>[]; pos: number; ready: number }).batch =
    batch;
  (cursor as unknown as { pos: number }).pos = 0;
  cursor.ready = 1;
  return batch.length;
}

export function idxNext(cursor: D9Cursor): Record<string, unknown> | null {
  const c = cursor as unknown as {
    batch: Record<string, unknown>[];
    pos: number;
    ready: number;
  };
  if (c.ready !== 1 || !c.batch) {
    return null;
  }
  if (c.pos >= c.batch.length) {
    return null;
  }
  const rec = c.batch[c.pos];
  c.pos += 1;
  return rec;
}

export function idxClose(cursor: D9Cursor): void {
  cursor.ready = 0;
}
