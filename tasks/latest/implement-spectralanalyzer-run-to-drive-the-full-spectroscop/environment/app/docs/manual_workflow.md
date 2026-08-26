# Damped Oscillator Spectrum Analysis — Output Reference

## JSON Report

Written to `/app/output/{sensorId}_analysis.json`. Fields: `sensorId`, `sampleRateHz`, `durationSec`, `damping`, `naturalFreqHz`, `rmsEnergy`, `dominantFrequencyHz`, `numSamples`, `apiMetadata`.

## CSV Spectrum

Written to `/app/output/{sensorId}_spectrum.csv`. Header: `frequencyHz,magnitudeDB`. One row per FFT bin.
