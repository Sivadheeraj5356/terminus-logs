import { NormalizationInfo, SpectrumPayload } from "./types";

export function normalizationInfo(payload: SpectrumPayload): NormalizationInfo {
  const liveTimeSec = payload.liveTimeSec ?? 1;
  const realTimeSec = payload.realTimeSec ?? liveTimeSec;
  return {
    liveTimeSec,
    realTimeSec,
    deadTimeCorrection: 1,
    backgroundSubtracted: false,
    backgroundScale: 0,
  };
}

export function observedRate(payload: SpectrumPayload, index: number): number {
  const info = normalizationInfo(payload);
  return payload.counts[index] / info.liveTimeSec;
}

export function rateVariance(payload: SpectrumPayload, index: number, readNoiseVariance: number): number {
  const info = normalizationInfo(payload);
  return (Math.max(payload.counts[index], 1) + readNoiseVariance) / (info.liveTimeSec * info.liveTimeSec);
}
