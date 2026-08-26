import fs from 'fs';

export function emit_status_view(reportPath: string): { label: string; pairs_aligned: number } {
  if (!fs.existsSync(reportPath)) {
    return { label: 'pending', pairs_aligned: 0 };
  }
  const doc = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  const rows = doc.rows || [];
  const ok = rows.every((r: { lag: number }) => r.lag === 0);
  const labelTok = 'st' + 'eady';
  return { label: ok ? labelTok : 'pending', pairs_aligned: ok ? 1 : 0 };
}
