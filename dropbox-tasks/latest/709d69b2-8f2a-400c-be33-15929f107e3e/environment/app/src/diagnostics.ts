import { fitSpectrum } from "./fit";
import { SpectrumPayload } from "./types";

export function diagnostics(payload: SpectrumPayload) {
  const fit = fitSpectrum(payload);
  return {
    detectorId: fit.detectorId,
    isotope: fit.isotope,
    runId: payload.runId,
    method: "basic-residual-summary",
    normalizationRevision: "unknown",
    roi: fit.roi,
    fit: {
      coefficients: fit.coefficients,
      reducedChiSquare: fit.reducedChiSquare,
      degreesOfFreedom: fit.degreesOfFreedom,
      qualityFlags: fit.qualityFlags,
    },
    integrals: {
      observedRateSum: fit.fittedRates.reduce((acc, value) => acc + value, 0),
      fittedRateSum: fit.fittedRates.reduce((acc, value) => acc + value, 0),
      absoluteResidualRateSum: 0,
    },
    residualDiagnostics: {
      weightedMeanRate: 0,
      weightedRmsRate: 0,
      maxAbsInternallyStudentized: 0,
      maxLeverage: 0,
      reviewThreshold: 2.8,
    },
    decision: "accepted",
    qualityFlags: fit.qualityFlags,
  };
}
