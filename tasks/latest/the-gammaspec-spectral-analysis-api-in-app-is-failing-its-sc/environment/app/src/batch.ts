import { fitSpectrum } from "./fit";
import { BatchFitPayload } from "./types";

export function batchFit(payload: BatchFitPayload) {
  if (!Array.isArray(payload.spectra)) throw new Error("spectra must be an array");
  const results = payload.spectra.map((spectrum) => ({
    runId: spectrum.runId,
    isotope: spectrum.isotope,
    fit: fitSpectrum(spectrum),
  }));
  return {
    detectorId: results[0]?.fit.detectorId ?? "unknown",
    runCount: results.length,
    sortedBy: "input",
    results,
  };
}
