export function themeHex(seed: number): string {
  const n = (seed * 2654435761) >>> 0;
  return ("000000" + n.toString(16)).slice(-6);
}
