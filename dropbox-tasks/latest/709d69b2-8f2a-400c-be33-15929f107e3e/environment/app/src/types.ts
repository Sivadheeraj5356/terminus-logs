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
