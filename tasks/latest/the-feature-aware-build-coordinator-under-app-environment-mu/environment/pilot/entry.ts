/**
 * bp_run driver entry and cert_digest reduction header.
 *
 * Reduction: fnv1a-64 over comma-joined sorted facet_material strings from terminal rows.
 * The summary cert_digest field must match this reduction on every coherent emit.
 * span_band is the maximum absolute lag magnitude across rows.
 */

import fs from 'fs';
import path from 'path';
import { emit_status_view } from '../tools/gauge_mux';
import { ledgerMtime } from '../engine/ledger_bridge';
import { fnv1a64, runPipeline, loadReportRows } from '../engine/pipeline';

const ENV_ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT_OUT = '/app/output/cert_report.json';

export function reduceFromRows(rows: Array<{ facet_material: string }>): string {
  const parts = rows.map((r) => r.facet_material).sort();
  return fnv1a64(parts.join(','));
}

function parseArgs(argv: string[]) {
  const out = { phase: 'all', drill: '', emit: DEFAULT_OUT, gauge: false, jobs: 0, clean: false };
  for (let i = 0; i < argv.length; i++) {
    const tok = argv[i];
    if (tok === '--phase') out.phase = argv[++i];
    else if (tok === '--drill') out.drill = argv[++i];
    else if (tok === '--emit') out.emit = argv[++i];
    else if (tok === '--jobs') out.jobs = parseInt(argv[++i], 10);
    else if (tok === '--gauge') out.gauge = true;
    else if (tok === '--clean') out.clean = true;
  }
  return out;
}

export function main(argv?: string[]): number {
  const args = parseArgs(argv || process.argv.slice(2));
  const outReport = path.resolve(args.emit);
  const outTraces = path.join(path.dirname(outReport), 'run_traces');
  if (args.gauge) {
    const view = emit_status_view(outReport);
    process.stdout.write(JSON.stringify(view) + '\n');
    return 0;
  }
  if (args.phase !== 'all') {
    process.stderr.write('only --phase all is supported in this build\n');
    return 2;
  }
  if (args.clean) {
    const buildDir = path.join(ENV_ROOT, 'build');
    if (fs.existsSync(buildDir)) {
      fs.rmSync(buildDir, { recursive: true, force: true });
    }
  }
  const ledgerPath = path.join(ENV_ROOT, 'state', 'k3_ledger.tsv');
  const before = ledgerMtime(ledgerPath);
  const doc = runPipeline(outReport, outTraces, {
    drill: args.drill || null,
    jobs: args.jobs || undefined,
  });
  const after = ledgerMtime(ledgerPath);
  if (args.drill === 'profile_a' && after < before) {
    return 3;
  }
  const digest = reduceFromRows(doc.rows);
  if (digest !== doc.summary.cert_digest) {
    return 4;
  }
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
