import { fitSpectrum } from "./fit";
import { IsotopeScreenPayload } from "./types";

export function isotopeScreen(payload: IsotopeScreenPayload) {
  const candidates = payload.candidateIsotopes.map((isotope, index) => {
    const fit = fitSpectrum({ ...payload.spectrum, isotope });
    return {
      rank: index + 1,
      isotope,
      aicc: fit.reducedChiSquare,
      deltaAicc: 0,
      amplitude: fit.coefficients.amplitude,
      reducedChiSquare: fit.reducedChiSquare,
      roi: fit.roi,
      qualityFlags: fit.qualityFlags,
    };
  });
  return {
    detectorId: candidates.length ? "GS-ORION-17" : "unknown",
    method: "candidate-screen",
    candidateCount: candidates.length,
    sortedBy: "input",
    candidates,
  };
}
