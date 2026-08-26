import { fitSpectrum } from "./fit";
import { SpectrumPayload } from "./types";

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export interface BootstrapPayload extends SpectrumPayload {
  seed: number;
  iterations: number;
}

export function bootstrapSpectrum(payload: BootstrapPayload) {
  const fit = fitSpectrum(payload);
  const samples: number[] = [];
  for (let i = 0; i < payload.iterations; i += 1) {
    const counts = payload.counts.map((count) => count + (Math.random() - 0.5) * Math.sqrt(Math.max(count, 1)));
    const sampleFit = fitSpectrum({ ...payload, counts });
    samples.push(sampleFit.coefficients.amplitude);
  }
  return {
    detectorId: fit.detectorId,
    isotope: fit.isotope,
    seed: payload.seed,
    iterations: payload.iterations,
    statistic: "amplitude",
    pointEstimate: fit.coefficients.amplitude,
    confidence: {
      ci68: [percentile(samples, 0.16), percentile(samples, 0.84)],
      ci95: [percentile(samples, 0.025), percentile(samples, 0.975)],
    },
  };
}
