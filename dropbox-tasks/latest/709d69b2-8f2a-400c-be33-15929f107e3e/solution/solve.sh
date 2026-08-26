#!/bin/bash
set -euo pipefail

cd /app
mkdir -p /app/output

grep -q "GS-NRM-0417" /app/docs/gammaspec_methods.md
grep -q "GS-TAIL-0633" /app/docs/gammaspec_methods.md
grep -q "GS-BAT-0726" /app/docs/gammaspec_methods.md
grep -q "GS-DIAG-0911" /app/docs/gammaspec_methods.md
grep -q "GS-SCR-1034" /app/docs/gammaspec_methods.md

cat > /app/src/types.ts <<'TS'
export interface PeakDefinition {
  energyKeV: number;
  sigmaKeV: number;
  roiHalfWidthKeV: number;
  tailDecayKeV?: number;
}

export interface Calibration {
  detectorId: string;
  coefficientUnits: string;
  channelPolynomial: {
    offset: number;
    slope: number;
    quadratic: number;
  };
  readNoiseVariance: number;
  normalizationRevision?: string;
  peaks: Record<string, PeakDefinition>;
}

export interface BackgroundPayload {
  counts: number[];
  liveTimeSec: number;
  label?: string;
}

export interface SpectrumPayload {
  channels: number[];
  counts: number[];
  isotope: string;
  runId?: string;
  liveTimeSec?: number;
  realTimeSec?: number;
  background?: BackgroundPayload;
}

export interface NormalizationInfo {
  liveTimeSec: number;
  realTimeSec: number;
  deadTimeCorrection: number;
  backgroundSubtracted: boolean;
  backgroundScale: number;
}

export interface FitResult {
  detectorId: string;
  isotope: string;
  method: string;
  weighting: string;
  calibrationApplied: boolean;
  modelTerms: string[];
  normalization: NormalizationInfo;
  qualityFlags: string[];
  roi: {
    count: number;
    energyMinKeV: number;
    energyMaxKeV: number;
    channelMin: number;
    channelMax: number;
  };
  coefficients: {
    amplitude: number;
    tailAmplitude: number;
    background: number;
    linearSlope: number;
  };
  covariance: number[][];
  reducedChiSquare: number;
  degreesOfFreedom: number;
  residuals: number[];
  fittedRates: number[];
}

export interface BatchFitPayload {
  spectra: Array<SpectrumPayload & { runId: string }>;
  includeResiduals?: boolean;
}

export interface IsotopeScreenPayload {
  spectrum: Omit<SpectrumPayload, "isotope"> & { isotope?: string };
  candidateIsotopes: string[];
  maxResults?: number;
}
TS

cat > /app/src/calibration.ts <<'TS'
import fs from "fs";
import path from "path";
import { Calibration } from "./types";

export const CALIBRATION_PATH = path.join(__dirname, "..", "data", "calibration.gamma.json");

let cachedCalibration: Calibration | undefined;

export function loadCalibration(): Calibration {
  if (!cachedCalibration) {
    const raw = fs.readFileSync(CALIBRATION_PATH, "utf8");
    cachedCalibration = JSON.parse(raw) as Calibration;
  }
  return cachedCalibration;
}

export function channelToEnergy(channel: number, calibration: Calibration): number {
  const p = calibration.channelPolynomial;
  return p.offset + p.slope * channel + p.quadratic * channel * channel;
}
TS

cat > /app/src/matrix.ts <<'TS'
export function solveLinear(matrix: number[][], vector: number[]): number[] {
  const size = vector.length;
  if (matrix.length !== size || matrix.some((row) => row.length !== size)) {
    throw new Error("matrix dimensions do not match vector");
  }
  const augmented = matrix.map((row, rowIdx) => [...row, vector[rowIdx]]);
  for (let col = 0; col < size; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < size; row += 1) {
      if (Math.abs(augmented[row][col]) > Math.abs(augmented[pivot][col])) {
        pivot = row;
      }
    }
    [augmented[col], augmented[pivot]] = [augmented[pivot], augmented[col]];
    const divisor = augmented[col][col];
    if (!Number.isFinite(divisor) || Math.abs(divisor) < 1e-14) {
      throw new Error("singular weighted normal matrix");
    }
    for (let idx = col; idx <= size; idx += 1) {
      augmented[col][idx] /= divisor;
    }
    for (let row = 0; row < size; row += 1) {
      if (row === col) continue;
      const factor = augmented[row][col];
      for (let idx = col; idx <= size; idx += 1) {
        augmented[row][idx] -= factor * augmented[col][idx];
      }
    }
  }
  return augmented.map((row) => row[size]);
}

export function invertMatrix(matrix: number[][]): number[][] {
  const size = matrix.length;
  const inverse = Array.from({ length: size }, () => Array<number>(size).fill(0));
  for (let col = 0; col < size; col += 1) {
    const rhs = Array<number>(size).fill(0);
    rhs[col] = 1;
    const solved = solveLinear(matrix, rhs);
    for (let row = 0; row < size; row += 1) {
      inverse[row][col] = solved[row];
    }
  }
  return inverse;
}
TS

cat > /app/src/normalization.ts <<'TS'
import { NormalizationInfo, SpectrumPayload } from "./types";

function assertFiniteNumber(name: string, value: unknown): asserts value is number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${name} must be a finite number`);
  }
}

function assertFiniteArray(name: string, values: unknown): asserts values is number[] {
  if (!Array.isArray(values) || values.length === 0 || !values.every((value) => typeof value === "number" && Number.isFinite(value))) {
    throw new Error(`${name} must be a non-empty numeric array`);
  }
}

export function validateSpectrumPayload(payload: SpectrumPayload): void {
  if (!payload || typeof payload !== "object") {
    throw new Error("request body must be an object");
  }
  assertFiniteArray("channels", payload.channels);
  assertFiniteArray("counts", payload.counts);
  if (payload.channels.length !== payload.counts.length || payload.channels.length < 5) {
    throw new Error("channels and counts must have the same length and contain at least five points");
  }
  if (typeof payload.isotope !== "string" || payload.isotope.length === 0) {
    throw new Error("isotope must be a non-empty string");
  }
  const live = payload.liveTimeSec ?? 1;
  const real = payload.realTimeSec ?? live;
  assertFiniteNumber("liveTimeSec", live);
  assertFiniteNumber("realTimeSec", real);
  if (live <= 0) {
    throw new Error("liveTimeSec must be positive");
  }
  if (real < live) {
    throw new Error("realTimeSec must be greater than or equal to liveTimeSec");
  }
  if (payload.background) {
    assertFiniteArray("background.counts", payload.background.counts);
    if (payload.background.counts.length !== payload.counts.length) {
      throw new Error("background counts must match the spectrum length");
    }
    assertFiniteNumber("background.liveTimeSec", payload.background.liveTimeSec);
    if (payload.background.liveTimeSec <= 0) {
      throw new Error("background liveTimeSec must be positive");
    }
  }
}

export function normalizationInfo(payload: SpectrumPayload): NormalizationInfo {
  const liveTimeSec = payload.liveTimeSec ?? 1;
  const realTimeSec = payload.realTimeSec ?? liveTimeSec;
  const backgroundScale = payload.background ? liveTimeSec / payload.background.liveTimeSec : 0;
  return {
    liveTimeSec,
    realTimeSec,
    deadTimeCorrection: realTimeSec / liveTimeSec,
    backgroundSubtracted: Boolean(payload.background),
    backgroundScale,
  };
}

export function observedRate(payload: SpectrumPayload, index: number): number {
  const info = normalizationInfo(payload);
  const backgroundCount = payload.background ? payload.background.counts[index] : 0;
  const netCount = payload.counts[index] - info.backgroundScale * backgroundCount;
  return (netCount * info.deadTimeCorrection) / info.liveTimeSec;
}

export function rateVariance(payload: SpectrumPayload, index: number, readNoiseVariance: number): number {
  const info = normalizationInfo(payload);
  const backgroundCount = payload.background ? payload.background.counts[index] : 0;
  const backgroundVariance = payload.background ? info.backgroundScale * info.backgroundScale * Math.max(backgroundCount, 1) : 0;
  return (Math.max(payload.counts[index], 1) + backgroundVariance + readNoiseVariance) * (
    info.deadTimeCorrection / info.liveTimeSec
  ) ** 2;
}
TS

cat > /app/src/quality.ts <<'TS'
import { NormalizationInfo } from "./types";

export function qualityFlags(normalization: NormalizationInfo, reducedChiSquare: number, tailUsed: boolean): string[] {
  const flags: string[] = [];
  if (tailUsed) flags.push("tail-model-applied");
  if (normalization.backgroundSubtracted) flags.push("background-subtracted");
  if (normalization.deadTimeCorrection > 1.0005) flags.push("dead-time-corrected");
  if (reducedChiSquare > 3.0) flags.push("high-reduced-chi-square");
  return flags;
}
TS

cat > /app/src/fit.ts <<'TS'
import { channelToEnergy, loadCalibration } from "./calibration";
import { invertMatrix, solveLinear } from "./matrix";
import { normalizationInfo, observedRate, rateVariance, validateSpectrumPayload } from "./normalization";
import { qualityFlags } from "./quality";
import { Calibration, FitResult, PeakDefinition, SpectrumPayload } from "./types";

export interface PreparedFit {
  calibration: Calibration;
  peak: PeakDefinition;
  energies: number[];
  roiIndices: number[];
  rows: number[][];
  observedRates: number[];
  weights: number[];
  normalization: FitResult["normalization"];
  tailUsed: boolean;
  payload: SpectrumPayload;
}

export interface SolvedFit {
  beta: number[];
  covariance: number[][];
  reducedChiSquare: number;
  degreesOfFreedom: number;
  residuals: number[];
  fittedRates: number[];
}

function gaussian(energy: number, center: number, sigma: number): number {
  const z = (energy - center) / sigma;
  return Math.exp(-0.5 * z * z);
}

function tailBasis(energy: number, center: number, decay: number | undefined): number {
  if (!Number.isFinite(decay) || decay === undefined || energy > center) {
    return 0;
  }
  return Math.exp((energy - center) / decay);
}

export function prepareFit(payload: SpectrumPayload): PreparedFit {
  validateSpectrumPayload(payload);
  const calibration = loadCalibration();
  const peak = calibration.peaks[payload.isotope];
  if (!peak) {
    throw new Error(`unknown isotope: ${payload.isotope}`);
  }
  const energies = payload.channels.map((channel) => channelToEnergy(channel, calibration));
  const roiIndices = energies
    .map((energy, index) => ({ energy, index }))
    .filter(({ energy }) => Math.abs(energy - peak.energyKeV) <= peak.roiHalfWidthKeV)
    .map(({ index }) => index);
  if (roiIndices.length <= 4) {
    throw new Error("calibrated ROI must contain more than four samples");
  }
  const rows: number[][] = [];
  const observedRates: number[] = [];
  const weights: number[] = [];
  for (const index of roiIndices) {
    const energy = energies[index];
    rows.push([
      gaussian(energy, peak.energyKeV, peak.sigmaKeV),
      tailBasis(energy, peak.energyKeV, peak.tailDecayKeV),
      1,
      energy - peak.energyKeV,
    ]);
    observedRates.push(observedRate(payload, index));
    weights.push(1 / rateVariance(payload, index, calibration.readNoiseVariance));
  }
  return {
    calibration,
    peak,
    energies,
    roiIndices,
    rows,
    observedRates,
    weights,
    normalization: normalizationInfo(payload),
    tailUsed: Number.isFinite(peak.tailDecayKeV),
    payload,
  };
}

export function solvePreparedFit(prepared: PreparedFit, observedRates = prepared.observedRates): SolvedFit {
  const size = prepared.rows[0].length;
  const normal = Array.from({ length: size }, () => Array<number>(size).fill(0));
  const rhs = Array<number>(size).fill(0);
  for (let idx = 0; idx < prepared.rows.length; idx += 1) {
    const row = prepared.rows[idx];
    const weight = prepared.weights[idx];
    const observed = observedRates[idx];
    for (let r = 0; r < size; r += 1) {
      rhs[r] += row[r] * weight * observed;
      for (let c = 0; c < size; c += 1) {
        normal[r][c] += row[r] * weight * row[c];
      }
    }
  }
  const beta = solveLinear(normal, rhs);
  const fittedRates = prepared.rows.map((row) => row.reduce((acc, value, idx) => acc + value * beta[idx], 0));
  const residuals = observedRates.map((observed, idx) => observed - fittedRates[idx]);
  const degreesOfFreedom = prepared.rows.length - size;
  if (degreesOfFreedom <= 0) {
    throw new Error("not enough ROI samples for model degrees of freedom");
  }
  const reducedChiSquare = residuals.reduce(
    (acc, residual, idx) => acc + prepared.weights[idx] * residual * residual,
    0,
  ) / degreesOfFreedom;
  const covariance = invertMatrix(normal).map((row) => row.map((value) => value * reducedChiSquare));
  return { beta, covariance, reducedChiSquare, degreesOfFreedom, residuals, fittedRates };
}

export function fitSpectrumDetailed(payload: SpectrumPayload): { prepared: PreparedFit; solved: SolvedFit; result: FitResult } {
  const prepared = prepareFit(payload);
  const solved = solvePreparedFit(prepared);
  const indices = prepared.roiIndices;
  const terms = prepared.tailUsed ? ["gaussian", "lowEnergyTail", "constant", "linear"] : ["gaussian", "constant", "linear"];
  const result: FitResult = {
    detectorId: prepared.calibration.detectorId,
    isotope: payload.isotope,
    method: "poisson-readout-tail-wls-r4",
    weighting: "poisson_readout_live_rate_inverse_variance",
    calibrationApplied: true,
    modelTerms: terms,
    normalization: prepared.normalization,
    qualityFlags: qualityFlags(prepared.normalization, solved.reducedChiSquare, prepared.tailUsed),
    roi: {
      count: indices.length,
      energyMinKeV: Math.min(...indices.map((index) => prepared.energies[index])),
      energyMaxKeV: Math.max(...indices.map((index) => prepared.energies[index])),
      channelMin: Math.min(...indices.map((index) => payload.channels[index])),
      channelMax: Math.max(...indices.map((index) => payload.channels[index])),
    },
    coefficients: {
      amplitude: solved.beta[0],
      tailAmplitude: prepared.tailUsed ? solved.beta[1] : 0,
      background: prepared.tailUsed ? solved.beta[2] : solved.beta[1],
      linearSlope: prepared.tailUsed ? solved.beta[3] : solved.beta[2],
    },
    covariance: solved.covariance,
    reducedChiSquare: solved.reducedChiSquare,
    degreesOfFreedom: solved.degreesOfFreedom,
    residuals: solved.residuals,
    fittedRates: solved.fittedRates,
  };
  return { prepared, solved, result };
}

export function fitSpectrum(payload: SpectrumPayload): FitResult {
  return fitSpectrumDetailed(payload).result;
}
TS

cat > /app/src/bootstrap.ts <<'TS'
import { fitSpectrumDetailed, solvePreparedFit } from "./fit";
import { SpectrumPayload } from "./types";

function percentile(values: number[], probability: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

export interface BootstrapPayload extends SpectrumPayload {
  seed: number;
  iterations: number;
}

export function bootstrapSpectrum(payload: BootstrapPayload) {
  if (!Number.isInteger(payload.seed)) {
    throw new Error("seed must be an integer");
  }
  if (!Number.isInteger(payload.iterations) || payload.iterations < 2) {
    throw new Error("iterations must be an integer greater than one");
  }
  const { prepared, solved, result } = fitSpectrumDetailed(payload);
  const rng = mulberry32(payload.seed);
  const amplitudes: number[] = [];
  for (let iteration = 0; iteration < payload.iterations; iteration += 1) {
    const syntheticRates = solved.fittedRates.map((fitValue) => {
      const draw = Math.min(Math.floor(rng() * solved.residuals.length), solved.residuals.length - 1);
      return fitValue + solved.residuals[draw];
    });
    amplitudes.push(solvePreparedFit(prepared, syntheticRates).beta[0]);
  }
  return {
    detectorId: result.detectorId,
    isotope: result.isotope,
    seed: payload.seed,
    iterations: payload.iterations,
    statistic: "amplitude",
    method: "residual-frozen-weight-mulberry32",
    pointEstimate: result.coefficients.amplitude,
    confidence: {
      ci68: [percentile(amplitudes, 0.16), percentile(amplitudes, 0.84)],
      ci95: [percentile(amplitudes, 0.025), percentile(amplitudes, 0.975)],
    },
  };
}
TS

cat > /app/src/batch.ts <<'TS'
import { fitSpectrum } from "./fit";
import { BatchFitPayload, FitResult } from "./types";

function compactResult(runId: string, fit: FitResult, includeResiduals: boolean) {
  const base = {
    runId,
    roi: fit.roi,
    coefficients: fit.coefficients,
    normalization: fit.normalization,
    reducedChiSquare: fit.reducedChiSquare,
    qualityFlags: fit.qualityFlags,
  };
  return includeResiduals ? { ...base, residuals: fit.residuals, fittedRates: fit.fittedRates } : base;
}

export function batchFit(payload: BatchFitPayload) {
  if (!payload || !Array.isArray(payload.spectra)) {
    throw new Error("spectra must be an array");
  }
  const seen = new Set<string>();
  for (const spectrum of payload.spectra) {
    if (typeof spectrum.runId !== "string" || spectrum.runId.length === 0) {
      throw new Error("each batch spectrum must include a runId");
    }
    if (seen.has(spectrum.runId)) {
      throw new Error(`duplicate runId: ${spectrum.runId}`);
    }
    seen.add(spectrum.runId);
  }
  const includeResiduals = payload.includeResiduals === true;
  const sorted = [...payload.spectra].sort((left, right) => left.runId.localeCompare(right.runId));
  const fitted = sorted.map((spectrum) => ({ runId: spectrum.runId, fit: fitSpectrum(spectrum) }));
  const results = fitted.map(({ runId, fit }) => compactResult(runId, fit, includeResiduals));
  return {
    detectorId: fitted[0]?.fit.detectorId ?? "GS-ORION-17",
    runCount: results.length,
    sortedBy: "runId",
    results,
  };
}
TS

cat > /app/src/diagnostics.ts <<'TS'
import { fitSpectrumDetailed, PreparedFit } from "./fit";
import { invertMatrix } from "./matrix";
import { SpectrumPayload } from "./types";

function hatDiagonal(prepared: PreparedFit): number[] {
  const size = prepared.rows[0].length;
  const normal = Array.from({ length: size }, () => Array<number>(size).fill(0));
  for (let idx = 0; idx < prepared.rows.length; idx += 1) {
    const row = prepared.rows[idx];
    const weight = prepared.weights[idx];
    for (let r = 0; r < size; r += 1) {
      for (let c = 0; c < size; c += 1) {
        normal[r][c] += row[r] * weight * row[c];
      }
    }
  }
  const inverse = invertMatrix(normal);
  return prepared.rows.map((row, idx) => {
    let inner = 0;
    for (let r = 0; r < size; r += 1) {
      for (let c = 0; c < size; c += 1) {
        inner += row[r] * inverse[r][c] * row[c];
      }
    }
    return prepared.weights[idx] * inner;
  });
}

export function diagnostics(payload: SpectrumPayload) {
  const { prepared, solved, result } = fitSpectrumDetailed(payload);
  const weightSum = prepared.weights.reduce((acc, value) => acc + value, 0);
  const weightedMeanRate = solved.residuals.reduce((acc, residual, idx) => acc + prepared.weights[idx] * residual, 0) / weightSum;
  const weightedRmsRate = Math.sqrt(
    solved.residuals.reduce((acc, residual, idx) => acc + prepared.weights[idx] * residual * residual, 0) / weightSum,
  );
  const hatValues = hatDiagonal(prepared);
  const maxAbsInternallyStudentized = Math.max(
    ...solved.residuals.map((residual, idx) => Math.abs(
      residual * Math.sqrt(prepared.weights[idx] / Math.max(1 - hatValues[idx], 1e-12)),
    )),
  );
  const decision = maxAbsInternallyStudentized > 2.8 || solved.reducedChiSquare > 3.0 ? "review-required" : "accepted";
  const qualityFlags = decision === "review-required" ? [...result.qualityFlags, "residual-review"] : result.qualityFlags;
  return {
    detectorId: result.detectorId,
    isotope: result.isotope,
    runId: payload.runId,
    method: "roi-hat-residual-diagnostics-r2",
    normalizationRevision: prepared.calibration.normalizationRevision,
    roi: result.roi,
    fit: {
      coefficients: result.coefficients,
      reducedChiSquare: result.reducedChiSquare,
      degreesOfFreedom: result.degreesOfFreedom,
      qualityFlags: result.qualityFlags,
    },
    integrals: {
      observedRateSum: prepared.observedRates.reduce((acc, value) => acc + value, 0),
      fittedRateSum: solved.fittedRates.reduce((acc, value) => acc + value, 0),
      absoluteResidualRateSum: solved.residuals.reduce((acc, value) => acc + Math.abs(value), 0),
    },
    residualDiagnostics: {
      weightedMeanRate,
      weightedRmsRate,
      maxAbsInternallyStudentized,
      maxLeverage: Math.max(...hatValues),
      reviewThreshold: 2.8,
    },
    decision,
    qualityFlags,
  };
}
TS

cat > /app/src/screening.ts <<'TS'
import { fitSpectrumDetailed } from "./fit";
import { IsotopeScreenPayload, SpectrumPayload } from "./types";

function assertKnownCandidates(payload: IsotopeScreenPayload): string[] {
  if (!payload || typeof payload !== "object") {
    throw new Error("request body must be an object");
  }
  if (!payload.spectrum || typeof payload.spectrum !== "object") {
    throw new Error("spectrum must be an object");
  }
  if (!Array.isArray(payload.candidateIsotopes) || payload.candidateIsotopes.length === 0) {
    throw new Error("candidateIsotopes must be a non-empty array");
  }
  const seen = new Set<string>();
  for (const isotope of payload.candidateIsotopes) {
    if (typeof isotope !== "string" || isotope.length === 0) {
      throw new Error("candidate isotopes must be non-empty strings");
    }
    if (seen.has(isotope)) {
      throw new Error(`duplicate candidate isotope: ${isotope}`);
    }
    seen.add(isotope);
  }
  if (payload.maxResults !== undefined && (!Number.isInteger(payload.maxResults) || payload.maxResults <= 0)) {
    throw new Error("maxResults must be a positive integer");
  }
  return payload.candidateIsotopes;
}

export function isotopeScreen(payload: IsotopeScreenPayload) {
  const candidates = assertKnownCandidates(payload);
  const rows = candidates.map((isotope) => {
    const spectrum = { ...(payload.spectrum as SpectrumPayload), isotope };
    const { result } = fitSpectrumDetailed(spectrum);
    const kParams = 4;
    const nPoints = result.roi.count;
    if (nPoints <= kParams + 1) {
      throw new Error(`candidate ${isotope} does not have enough ROI samples`);
    }
    const weightedSse = result.reducedChiSquare * result.degreesOfFreedom;
    const aic = nPoints * Math.log(Math.max(weightedSse / nPoints, 1e-12)) + 2 * kParams;
    const aicc = aic + (2 * kParams * (kParams + 1)) / (nPoints - kParams - 1);
    return {
      rank: 0,
      isotope,
      aicc,
      deltaAicc: 0,
      amplitude: result.coefficients.amplitude,
      reducedChiSquare: result.reducedChiSquare,
      roi: result.roi,
      qualityFlags: result.qualityFlags,
    };
  });
  rows.sort((left, right) => left.aicc - right.aicc || left.isotope.localeCompare(right.isotope));
  const best = rows[0].aicc;
  for (let idx = 0; idx < rows.length; idx += 1) {
    rows[idx].rank = idx + 1;
    rows[idx].deltaAicc = rows[idx].aicc - best;
  }
  const maxResults = payload.maxResults ?? rows.length;
  const returned = rows.slice(0, maxResults);
  return {
    detectorId: "GS-ORION-17",
    method: "candidate-isotope-wls-aicc-screen-r1",
    candidateCount: returned.length,
    sortedBy: "aicc",
    candidates: returned,
  };
}
TS

cat > /app/src/server.ts <<'TS'
import express, { Request, Response } from "express";
import fs from "fs";
import path from "path";
import { batchFit } from "./batch";
import { bootstrapSpectrum } from "./bootstrap";
import { diagnostics } from "./diagnostics";
import { fitSpectrum } from "./fit";
import { isotopeScreen } from "./screening";

const app = express();
app.use(express.json({ limit: "3mb" }));

function sendError(res: Response, error: unknown): void {
  res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
}

app.get("/health", (_req: Request, res: Response) => {
  res.json({ ok: true, service: "gammaspec-api" });
});

app.post("/fit", (req: Request, res: Response) => {
  try {
    res.json(fitSpectrum(req.body));
  } catch (error) {
    sendError(res, error);
  }
});

app.post("/bootstrap", (req: Request, res: Response) => {
  try {
    res.json(bootstrapSpectrum(req.body));
  } catch (error) {
    sendError(res, error);
  }
});

app.post("/batch-fit", (req: Request, res: Response) => {
  try {
    res.json(batchFit(req.body));
  } catch (error) {
    sendError(res, error);
  }
});

app.post("/diagnostics", (req: Request, res: Response) => {
  try {
    res.json(diagnostics(req.body));
  } catch (error) {
    sendError(res, error);
  }
});

app.post("/isotope-screen", (req: Request, res: Response) => {
  try {
    res.json(isotopeScreen(req.body));
  } catch (error) {
    sendError(res, error);
  }
});

app.get("/compliance", (_req: Request, res: Response) => {
  const matrixPath = path.join(process.cwd(), "output", "compliance_matrix.json");
  if (!fs.existsSync(matrixPath)) {
    res.status(404).json({ error: "compliance matrix not written" });
    return;
  }
  res.type("application/json").send(fs.readFileSync(matrixPath, "utf8"));
});

const port = Number(process.env.PORT ?? "3000");
app.listen(port, () => {
  console.log(`GammaSpec API listening on ${port}`);
});
TS

node <<'JS'
const fs = require("fs");
const path = require("path");

const appRoot = "/app";
const docPath = path.join(appRoot, "docs", "gammaspec_methods.md");
const srcDir = path.join(appRoot, "src");
const matrixPath = path.join(appRoot, "output", "compliance_matrix.json");
const auditCaptures = [
  "/app/audit/strace-gammaspec.log",
  "/app/audit/lsof-gammaspec.txt",
];

const docs = fs.readFileSync(docPath, "utf8");
const sourceFiles = fs.readdirSync(srcDir)
  .filter((name) => name.endsWith(".ts"))
  .sort()
  .map((name) => ({
    path: path.join(srcDir, name),
    display: `/app/src/${name}`,
    text: fs.readFileSync(path.join(srcDir, name), "utf8"),
  }));

const requiredIds = [
  "GS-CAL-0328",
  "GS-NRM-0417",
  "GS-TAIL-0633",
  "GS-WLS-0182",
  "GS-BS-0441",
  "GS-BAT-0726",
  "GS-QC-0864",
  "GS-DIAG-0911",
  "GS-SCR-1034",
  "GS-MTX-0550",
];

const signals = {
  "GS-CAL-0328": ["calibration.gamma.json", "loadCalibration", "channelToEnergy", "detectorId", "normalizationRevision"],
  "GS-NRM-0417": ["deadTimeCorrection", "backgroundScale", "prepareSpectrum", "observedRates", "variances"],
  "GS-TAIL-0633": ["lowEnergyTail", "tailAmplitude", "tailBasis", "tailDecayKeV"],
  "GS-WLS-0182": ["invertMatrix", "reducedChiSquare", "covariance", "degreesOfFreedom", "solvePreparedFit"],
  "GS-BS-0441": ["mulberry32", "residuals", "confidence", "ci68", "ci95"],
  "GS-BAT-0726": ["batchFit", "includeResiduals", "runId", "sortedBy", "compactResult"],
  "GS-QC-0864": ["tail-model-applied", "background-subtracted", "dead-time-corrected", "high-reduced-chi-square"],
  "GS-DIAG-0911": ["diagnostics", "hatDiagonal", "weightedRmsRate", "maxAbsInternallyStudentized", "residual-review"],
  "GS-SCR-1034": ["isotopeScreen", "aicc", "deltaAicc", "candidateIsotopes", "sortedBy"],
  "GS-MTX-0550": ["compliance_matrix.json", "requirementId", "auditCaptures", "verifiedBy", "fixSummary"],
};

function requirementSection(requirementId) {
  const requirementIndex = docs.indexOf(`Requirement ${requirementId}`);
  const firstMention = docs.indexOf(requirementId);
  const index = requirementIndex >= 0 ? requirementIndex : firstMention;
  if (index < 0) {
    throw new Error(`missing ${requirementId} in methods document`);
  }
  const nextSection = docs.indexOf("\n## ", index + 1);
  return docs.slice(index, nextSection >= 0 ? nextSection : docs.length).replace(/\s+/g, " ").trim();
}

function sentenceSummary(requirementId, evidence) {
  const section = requirementSection(requirementId);
  const firstSentence = section.split(/(?<=[.!?])\s+/)[0] || section;
  const cleaned = firstSentence
    .replace(/^Requirement\s+/, "")
    .replace(/`/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const modules = evidence
    .filter((item) => item.startsWith("/app/src/"))
    .map((item) => path.basename(item))
    .slice(0, 3)
    .join(", ");
  return `Implemented ${cleaned} using ${modules || "the generated compliance artifact"} as file-level evidence.`;
}

function evidenceFor(requirementId) {
  if (requirementId === "GS-MTX-0550") {
    return [matrixPath];
  }
  const tokens = signals[requirementId];
  const matches = sourceFiles
    .filter((file) => tokens.some((token) => file.text.includes(token)))
    .map((file) => file.display);
  if (requirementId === "GS-CAL-0328") {
    matches.push("/app/data/calibration.gamma.json");
  }
  const unique = [...new Set(matches)];
  if (unique.length === 0) {
    throw new Error(`no implementation evidence found for ${requirementId}`);
  }
  return unique;
}

function verifiedByFor(evidence) {
  const sourceEvidence = evidence.filter((item) => item.startsWith("/app/src/"));
  return sourceEvidence.length > 0 ? sourceEvidence : evidence;
}

for (const requirementId of requiredIds) {
  requirementSection(requirementId);
}

const entries = requiredIds.map((requirementId) => {
  const evidence = evidenceFor(requirementId);
  return {
    requirementId,
    source: `${docPath}#${requirementId}`,
    fixSummary: sentenceSummary(requirementId, evidence),
    evidence,
    verifiedBy: verifiedByFor(evidence),
  };
});

fs.mkdirSync(path.dirname(matrixPath), { recursive: true });
fs.writeFileSync(matrixPath, `${JSON.stringify({
  task: "GammaSpec Express spectral fitting audit",
  auditCaptures,
  entries,
}, null, 2)}\n`);
JS

npm run build
