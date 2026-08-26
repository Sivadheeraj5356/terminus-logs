import { writeLedger, appendLedger, readLedger } from '../tools/ledger.mjs';

export function parkTip(root = process.cwd()) {
  const path = `${root}/state/migrate-journal.jsonl`;
  const events = readLedger(path);
  if (!events.length) {
    console.log(JSON.stringify({ resumed: false, mode: 'empty' }));
    return;
  }
  // drops committed history and uses stale abort reason
  writeLedger(path, []);
  appendLedger(path, {
    phase: 'ABORT',
    reason: 'interrupted_overlay_epoch',
    dropped: events.map((event) => event.phase),
  });
  console.log(JSON.stringify({ resumed: true, mode: 'wipe', dropped: events.length }));
}

parkTip();
