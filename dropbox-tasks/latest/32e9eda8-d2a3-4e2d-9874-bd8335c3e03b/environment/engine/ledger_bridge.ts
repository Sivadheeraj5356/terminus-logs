import fs from 'fs';

export function readLedger(ledgerPath: string): Record<string, string> {
  if (!fs.existsSync(ledgerPath)) return {};
  const out: Record<string, string> = {};
  for (const line of fs.readFileSync(ledgerPath, 'utf8').split('\n')) {
    if (!line.trim() || line.startsWith('aid')) continue;
    const [aid, hx] = line.split('\t');
    out[aid.trim()] = hx.trim();
  }
  return out;
}

export function writeLedger(ledgerPath: string, entries: Record<string, string>): void {
  const lines = ['aid\tproof_hex'];
  for (const aid of Object.keys(entries).sort()) {
    lines.push(`${aid}\t${entries[aid]}`);
  }
  fs.mkdirSync(require('path').dirname(ledgerPath), { recursive: true });
  fs.writeFileSync(ledgerPath, lines.join('\n') + '\n');
}

export function ledgerMtime(ledgerPath: string): number {
  if (!fs.existsSync(ledgerPath)) return 0;
  return fs.statSync(ledgerPath).mtimeMs;
}
