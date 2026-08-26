export function previewSlots(slots: Uint32Array): string {
  const bits: string[] = [];
  for (let i = 0; i < slots.length; i++) {
    bits.push("s" + i + "=" + slots[i]);
  }
  return bits.join(" ");
}
