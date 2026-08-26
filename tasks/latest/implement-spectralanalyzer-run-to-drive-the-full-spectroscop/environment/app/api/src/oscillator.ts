/**
 * Damped harmonic oscillator simulation.
 * Generates synthetic accelerometer readings for a
 * mass-spring-damper system driven by initial conditions.
 */

export interface SimulateParams {
  sampleRateHz: number;
  durationSec: number;
  damping: number;
  naturalFreqHz: number;
}

export interface FftBin {
  frequencyHz: number;
  magnitude: number;
}

export interface SimulateResult {
  sensorId: string;
  samples: number[];
  fftBins: FftBin[];
  sampleRateHz: number;
  durationSec: number;
}

/**
 * Simulates a damped harmonic oscillator response.
 */
export function simulateOscillator(params: SimulateParams): SimulateResult {
  const { sampleRateHz, durationSec, damping, naturalFreqHz } = params;
  const numSamples = Math.floor(sampleRateHz * durationSec);
  const dt = 1.0 / sampleRateHz;

  // Damped natural frequency
  const wd = 2 * Math.PI * naturalFreqHz * Math.sqrt(1 - damping * damping);

  // Initial amplitude
  const A = 1.0;
  const phi = 0.0;

  const samples: number[] = [];
  for (let i = 0; i < numSamples; i++) {
    const t = i * dt;
    const x = A * Math.exp(-damping * naturalFreqHz * t) * Math.sin(wd * t + phi) + 0.02;
    samples.push(x);
  }

  const fftBins = computeFFT(samples, sampleRateHz);

  return {
    sensorId: 'ACCEL-001',
    samples,
    fftBins,
    sampleRateHz,
    durationSec
  };
}

/**
 * Simple FFT-based spectrum analysis.
 * Pads signal to next power of two and computes magnitude spectrum.
 */
export function computeFFT(samples: number[], sampleRateHz: number): FftBin[] {
  const n = samples.length;
  const nextPow2 = 1 << (Math.ceil(Math.log2(n)));
  const padded = new Array(nextPow2).fill(0);
  for (let i = 0; i < n; i++) {
    padded[i] = samples[i];
  }

  const real = padded.slice();
  const imag = new Array(nextPow2).fill(0);
  fft(real, imag);

  const nyquist = sampleRateHz / 2;
  const bins: FftBin[] = [];
  for (let i = 0; i < nextPow2 / 2; i++) {
    const freq = (i * sampleRateHz) / nextPow2;
    const mag = Math.abs(real[i]);
    bins.push({ frequencyHz: parseFloat(freq.toFixed(4)), magnitude: parseFloat(mag.toFixed(8)) });
  }
  return bins;
}

/**
 * In-place iterative Cooley-Tukey FFT (radix-2).
 * Operates on real and imag arrays in place.
 */
function fft(real: number[], imag: number[]): void {
  const n = real.length;
  if (n <= 1) return;

  // Bit-reversal permutation
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) {
      j ^= bit;
    }
    j ^= bit;
    if (i < j) {
      [real[i], real[j]] = [real[j], real[i]];
      [imag[i], imag[j]] = [imag[j], imag[i]];
    }
  }

  // Butterfly computation
  for (let len = 2; len <= n; len <<= 1) {
    const angle = (-2 * Math.PI) / len;
    const wReal = Math.cos(angle);
    const wImag = Math.sin(angle);
    for (let i = 0; i < n; i += len) {
      let curReal = 1.0;
      let curImag = 0.0;
      for (let j = 0; j < len / 2; j++) {
        const uReal = real[i + j];
        const uImag = imag[i + j];
        const vReal = real[i + j + len / 2] * curReal - imag[i + j + len / 2] * curImag;
        const vImag = real[i + j + len / 2] * curImag + imag[i + j + len / 2] * curReal;
        real[i + j] = uReal + vReal;
        imag[i + j] = uImag + vImag;
        real[i + j + len / 2] = uReal - vReal;
        imag[i + j + len / 2] = uImag - vImag;
        const newReal = curReal * wReal - curImag * wImag;
        const newImag = curReal * wImag + curImag * wReal;
        curReal = newReal;
        curImag = newImag;
      }
    }
  }
}
