import { SpectrumPayload } from "./types";

export function qualityFlags(_payload: SpectrumPayload, reducedChiSquare: number, _tailUsed: boolean): string[] {
  const flags: string[] = [];
  if (reducedChiSquare > 4) flags.push("high-reduced-chi-square");
  return flags;
}
