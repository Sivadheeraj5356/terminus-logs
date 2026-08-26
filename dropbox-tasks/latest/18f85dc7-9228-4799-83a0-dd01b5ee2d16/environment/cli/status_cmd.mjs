import fs from 'node:fs';
import { estimateRegs } from '../passes/scan_est.mjs';

export function runStatusSync(tracePath) {
  try {
    const raw = JSON.parse(fs.readFileSync(tracePath, 'utf8'));
    return {
      phase: 'preview',
      register_estimate: estimateRegs(raw.records ?? []),
      message: 'local preview ready',
    };
  } catch {
    return { phase: 'preview', register_estimate: 0, message: 'no trace yet' };
  }
}
