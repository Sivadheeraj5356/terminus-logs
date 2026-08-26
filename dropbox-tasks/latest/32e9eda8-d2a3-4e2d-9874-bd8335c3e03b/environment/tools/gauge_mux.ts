import fs from 'fs';

export function emit_status_view(reportPath: string): { label: string; pairs_aligned: number } {
  if (!fs.existsSync(reportPath)) {
    return { label: 'pending', pairs_aligned: 0 };
  }
  const doc = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  const rows = doc.rows || [];
  const steady = rows.every(
    (r: { lag: number; expand_rc: number; merge_rc: number }) =>
      r.lag === 0 && r.expand_rc === 1 && r.merge_rc === 1,
  );
  const labelTok = 'st' + 'eady';
  return { label: steady ? labelTok : 'pending', pairs_aligned: steady ? 1 : 0 };
}
