import fs from 'fs';
import path from 'path';
import { buildArmStates } from './build_flags';
import { materializeRows } from './emit_certs';
import { writeLedger } from './ledger_bridge';

const ENV_ROOT = path.resolve(__dirname, '..', '..');
const DATA = path.join(ENV_ROOT, 'data');
const SCHEMA_ROW = 'row_v4';

type HoldEntry = { slug: string; tags: string[]; slot_rotate?: number; jobs?: number };

export function parseArmTable(armPath: string): string[] {
  return fs
    .readFileSync(armPath, 'utf8')
    .split('\n')
    .map((ln) => ln.trim())
    .filter(Boolean);
}

export function loadHoldEntries(): HoldEntry[] {
  const raw = fs.readFileSync(path.join(DATA, 'extra_flags.toml'), 'utf8');
  const holds: HoldEntry[] = [];
  let cur: HoldEntry | null = null;
  for (const line of raw.split('\n')) {
    const t = line.trim();
    if (t.startsWith('[[hold]]')) {
      if (cur) holds.push(cur);
      cur = { slug: '', tags: [] };
      continue;
    }
    if (!cur || !t || t.startsWith('#')) continue;
    const m = t.match(/^(\w+)\s*=\s*(.+)$/);
    if (!m) continue;
    let val: string | number | string[] = m[2].trim();
    if (typeof val === 'string' && val.startsWith('[')) {
      val = val
        .slice(1, -1)
        .split(',')
        .map((x) => x.trim().replace(/^"|"$/g, ''));
    } else if (typeof val === 'string' && val.startsWith('"')) {
      val = val.replace(/^"|"$/g, '');
    } else if (typeof val === 'string' && /^\d+$/.test(val)) {
      val = parseInt(val, 10);
    }
    (cur as Record<string, unknown>)[m[1]] = val;
  }
  if (cur) holds.push(cur);
  return holds;
}

export function expandArms(primary: string[]): string[] {
  const out: string[] = [];
  for (const aid of primary) {
    out.push(aid);
    out.push(`${aid}_echo`);
  }
  for (const hold of loadHoldEntries()) {
    const slug = hold.slug;
    const tags = hold.tags;
    const rotate = hold.slot_rotate || 0;
    for (let i = 0; i < tags.length; i++) {
      const tag = tags[(i + rotate) % tags.length];
      out.push(`${tag}~${slug}`);
    }
  }
  return out;
}

export function fnv1a64(text: string): string {
  let h = 0xcbf29ce484222325n;
  for (const b of Buffer.from(text, 'utf8')) {
    h ^= BigInt(b);
    h = (h * 0x100000001b3n) & 0xffffffffffffffffn;
  }
  return h.toString(16).padStart(16, '0');
}

export function summarize(rows: Array<Record<string, number | string>>) {
  const spanBand = rows.reduce((m, r) => Math.max(m, Math.abs(Number(r.lag))), 0);
  const parts = rows.map((r) => String(r.facet_material)).sort();
  const digest = fnv1a64(parts.join(','));
  const steady = rows.every(
    (r) =>
      Number(r.lag) === 0 &&
      Number(r.expand_rc) === 1 &&
      Number(r.merge_rc) === 1 &&
      Number(r.proof_rc) === 1,
  );
  return {
    rows_total: rows.length,
    span_band: spanBand,
    sync_label: steady ? 'steady' : 'drift',
    cert_digest: digest,
  };
}

export function runPipeline(outReport: string, outTraces: string, opts: { drill?: string | null; jobs?: number } = {}) {
  const drill = opts.drill || null;
  const jobs = opts.jobs || 8;
  const reportPath = path.resolve(outReport);
  const witnessRoot = path.join(path.dirname(reportPath), 'witness_meta');
  fs.mkdirSync(witnessRoot, { recursive: true });

  const holdEntries = loadHoldEntries();
  const primary = parseArmTable(path.join(ENV_ROOT, 'docs', 'primary_flags.txt'));
  const aidList = expandArms(primary);
  const { arms, ledger } = buildArmStates(aidList, jobs, witnessRoot, holdEntries);
  const ledgerPath = path.join(ENV_ROOT, 'state', 'k3_ledger.tsv');
  writeLedger(ledgerPath, ledger);
  const rows = materializeRows(arms, witnessRoot);
  const summary = summarize(rows);
  const doc = { schema_version: SCHEMA_ROW, summary, rows };
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(doc, null, 2) + '\n');
  fs.mkdirSync(outTraces, { recursive: true });
  const trace = {
    phase_order: ['expand', 'merge', 'proof', 'emit'],
    row_count: rows.length,
    drill: drill || 'none',
    jobs,
    ledger_mtime: fs.existsSync(ledgerPath) ? fs.statSync(ledgerPath).mtimeMs : 0,
  };
  fs.writeFileSync(path.join(outTraces, 'last.json'), JSON.stringify(trace, null, 2) + '\n');
  return doc;
}

export function loadReportRows(reportPath: string) {
  if (!fs.existsSync(reportPath)) return [];
  return JSON.parse(fs.readFileSync(reportPath, 'utf8')).rows || [];
}
