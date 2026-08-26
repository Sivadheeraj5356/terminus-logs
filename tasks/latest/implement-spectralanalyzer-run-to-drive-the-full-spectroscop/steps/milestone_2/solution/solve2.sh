#!/bin/bash
set -euo pipefail

# Rewrite oscillator.ts completely with the corrected implementation.
# Using a full-file heredoc is more robust than fragile sed substitutions
# that break on formatting or whitespace changes.
cat > /app/api/src/oscillator.ts << 'TYPESCRIPT'
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
 *
 * Changed from the buggy version:
 *   1. Uses wn = 2*pi*naturalFreqHz (rad/s) in the exponential decay,
 *      not naturalFreqHz (Hz).  The damping envelope must use angular
 *      frequency so the exponent is dimensionless.
 *   2. Removed the spurious +0.02 DC offset that biased the signal.
 */
export function simulateOscillator(params: SimulateParams): SimulateResult {
  const { sampleRateHz, durationSec, damping, naturalFreqHz } = params;
  const numSamples = Math.floor(sampleRateHz * durationSec);
  const dt = 1.0 / sampleRateHz;

  // Angular natural frequency (rad/s) — needed for correct damping envelope
  const wn = 2 * Math.PI * naturalFreqHz;
  // Damped natural frequency (rad/s)
  const wd = wn * Math.sqrt(1 - damping * damping);

  // Initial amplitude
  const A = 1.0;
  const phi = 0.0;

  const samples: number[] = [];
  for (let i = 0; i < numSamples; i++) {
    const t = i * dt;
    // Correct damping envelope: exp(-zeta * wn * t), no DC bias
    const x = A * Math.exp(-damping * wn * t) * Math.sin(wd * t + phi);
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
 *
 * Changed from the buggy version:
 *   3. FFT magnitude now uses sqrt(real^2 + imag^2) instead of
 *      just Math.abs(real), so Parseval's theorem is satisfied.
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

  const bins: FftBin[] = [];
  for (let i = 0; i < nextPow2 / 2; i++) {
    const freq = (i * sampleRateHz) / nextPow2;
    // Magnitude must include both real and imaginary parts for Parseval
    const mag = Math.sqrt(real[i] * real[i] + imag[i] * imag[i]);
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
TYPESCRIPT

cat > /app/.fix-applied << 'EOF'
oscillator.ts:
  1. Fixed damping exponential term to use wn (rad/s) instead of naturalFreqHz (Hz)
  2. Fixed FFT magnitude to include imaginary component (was using only real part, breaking Parseval)
  3. Removed DC bias (+0.02) from the oscillator output
EOF

cd /app/api && npx tsc
cd /app/api && node dist/index.js &

# Wait for API to be ready (up to 30s)
for i in $(seq 1 30); do
    curl -s http://localhost:3000/health >/dev/null 2>&1 && break
    sleep 1
done
