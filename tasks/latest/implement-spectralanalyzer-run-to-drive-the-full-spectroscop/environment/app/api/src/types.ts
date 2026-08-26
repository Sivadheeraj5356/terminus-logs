export interface ApiMetadata {
  apiVersion: string;
  simulator: string;
  supportedUnits: string[];
  fftMethod: string;
  maxSamples: number;
}

export interface SimulateRequest {
  sampleRateHz: number;
  durationSec: number;
  damping: number;
  naturalFreqHz: number;
}

export interface SimulateResponse {
  sensorId: string;
  samples: number[];
  fftBins: FftBin[];
  sampleRateHz: number;
  durationSec: number;
}

export interface FftBin {
  frequencyHz: number;
  magnitude: number;
}

export interface AnalysisReport {
  sensorId: string;
  sampleRateHz: number;
  durationSec: number;
  damping: number;
  naturalFreqHz: number;
  rmsEnergy: number;
  dominantFrequencyHz: number;
  numSamples: number;
  apiMetadata: ApiMetadata;
}
