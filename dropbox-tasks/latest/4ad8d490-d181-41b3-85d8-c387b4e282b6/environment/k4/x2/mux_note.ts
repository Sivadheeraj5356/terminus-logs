// inventory note buffer; not on the emit path
export function mux_note(slices: string[]): string[] {
  const out: string[] = [];
  for (const s of slices) {
    if (s.length > 0) out.push(`note:${s.length}`);
  }
  return out;
}
