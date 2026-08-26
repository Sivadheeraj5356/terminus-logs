import { channelToEnergy, loadCalibration } from "./calibration";
import { invert3, solve3 } from "./matrix";
import { observedRate, rateVariance, normalizationInfo } from "./normalization";
import { qualityFlags } from "./quality";
import { FitResult, SpectrumPayload } from "./types";

function gaussian(energy: number, center: number, sigma: number): number {
  const z = (energy - center) / sigma;
  return Math.exp(-0.5 * z * z);
}

export function fitSpectrum(payload: SpectrumPayload): FitResult {
  const calibration = loadCalibration();
  const peak = calibration.peaks[payload.isotope];
  if (!peak) throw new Error(`unknown isotope: ${payload.isotope}`);
  if (payload.channels.length !== payload.counts.length || payload.channels.length < 4) {
    throw new Error("channels and counts must have the same length and contain at least four points");
  }
  const energies = payload.channels.map((channel) => channelToEnergy(channel, calibration));
  const indices = energies
    .map((energy, index) => ({ energy, index }))
    .filter(({ energy }) => Math.abs(energy - peak.energyKeV) <= peak.roiHalfWidthKeV)
    .map(({ index }) => index);
  if (indices.length <= 3) throw new Error("ROI must contain more than three samples");

  const normal = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const rhs = [0, 0, 0];
  const rows: number[][] = [];
  const observed: number[] = [];
  const weights: number[] = [];
  for (const index of indices) {
    const energy = energies[index];
    const row = [gaussian(energy, peak.energyKeV, peak.sigmaKeV), 1, energy - peak.energyKeV];
    const y = observedRate(payload, index);
    const weight = 1 / rateVariance(payload, index, calibration.readNoiseVariance);
    rows.push(row);
    observed.push(y);
    weights.push(weight);
    for (let r = 0; r < 3; r += 1) {
      rhs[r] += row[r] * weight * y;
      for (let c = 0; c < 3; c += 1) normal[r][c] += row[r] * weight * row[c];
    }
  }
  const beta = solve3(normal, rhs);
  const fittedRates = rows.map((row) => row.reduce((acc, value, idx) => acc + value * beta[idx], 0));
  const residuals = observed.map((value, idx) => value - fittedRates[idx]);
  const degreesOfFreedom = Math.max(rows.length - 2, 1);
  const reducedChiSquare = residuals.reduce((acc, residual, idx) => acc + weights[idx] * residual * residual, 0) / degreesOfFreedom;
  const covariance = invert3(normal).map((row) => row.map((value) => value * reducedChiSquare));

  return {
    detectorId: calibration.detectorId,
    isotope: payload.isotope,
    method: "poisson-readout-wls-v2",
    weighting: "poisson_readout_inverse_variance",
    calibrationApplied: true,
    modelTerms: ["gaussian", "constant", "linear"],
    normalization: normalizationInfo(payload),
    qualityFlags: qualityFlags(payload, reducedChiSquare, false),
    roi: {
      count: rows.length,
      energyMinKeV: Math.min(...indices.map((index) => energies[index])),
      energyMaxKeV: Math.max(...indices.map((index) => energies[index])),
      channelMin: Math.min(...indices.map((index) => payload.channels[index])),
      channelMax: Math.max(...indices.map((index) => payload.channels[index])),
    },
    coefficients: {
      amplitude: beta[0],
      tailAmplitude: 0,
      background: beta[1],
      linearSlope: beta[2],
    },
    covariance,
    reducedChiSquare,
    degreesOfFreedom,
    residuals,
    fittedRates,
  };
}
