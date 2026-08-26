#!/bin/bash
set -euo pipefail

cd /app

# Fix 1: calibration.toml — switch to exact Bose model, zero temperature offset
python3 << 'PYEOF'
path = "config/calibration.toml"
with open(path) as f:
    src = f.read()

old = 'bose_model = "approx"'
assert old in src, "bose_model approx not found"
src = src.replace(old, 'bose_model = "exact"', 1)

old = 'temperature_offset = 5.0'
assert old in src, "temperature_offset 5.0 not found"
src = src.replace(old, 'temperature_offset = 0.0', 1)

with open(path, 'w') as f:
    f.write(src)
PYEOF

# Fix 2: pkg/spectrum/loader.go — replace approx Bose factor with exact Bose-Einstein
python3 << 'PYEOF'
path = "pkg/spectrum/loader.go"
with open(path) as f:
    src = f.read()

old = '''func ComputeBoseFactor(wavenumberCm float64, temperatureK float64, cfg *config.Config) float64 {
	nuHz := wavenumberCm * 100.0 * 299792458.0
	exponent := 6.62607015e-34 * nuHz / (1.380649e-23 * temperatureK)
	if exponent > 700 {
		exponent = 700
	}
	bose := 1.0 / (expApprox(exponent) - 1.0)
	if cfg.BoseModel == "approx" {
		return expApprox(-exponent)
	}
	return bose
}'''

new = '''func ComputeBoseFactor(wavenumberCm float64, temperatureK float64, cfg *config.Config) float64 {
	nuHz := wavenumberCm * 100.0 * 299792458.0
	exponent := 6.62607015e-34 * nuHz / (1.380649e-23 * temperatureK)
	if exponent > 700 {
		exponent = 700
	}
	return 1.0 / (expApprox(exponent) - 1.0)
}'''

assert old in src, "ComputeBoseFactor function not found"
src = src.replace(old, new, 1)

with open(path, 'w') as f:
    f.write(src)
PYEOF

# Fix 3: pkg/spectrum/loader.go — fix TemperatureFromRatio to use detected shift,
# remove temperature offset, use correct inversion
python3 << 'PYEOF'
path = "pkg/spectrum/loader.go"
with open(path) as f:
    src = f.read()

old = '''func TemperatureFromRatio(ratio float64, laserNu float64, shiftCm float64, cfg *config.Config) float64 {
	if ratio <= 0 {
		return cfg.TemperatureOffset
	}
	nuPlus := laserNu + shiftCm
	nuMinus := laserNu - shiftCm
	if nuPlus <= 0 || nuMinus <= 0 {
		return cfg.TemperatureOffset
	}
	freqFactor := nuMinus / nuPlus
	freqFactorPow := 1.0
	exp := cfg.FrequencyExponent
	for i := 0; i < int(exp); i++ {
		freqFactorPow *= freqFactor
	}
	correction := ratio * freqFactorPow
	if correction <= 0 {
		return cfg.TemperatureOffset
	}
	lnCorr := natLog(correction)
	if lnCorr <= 0 {
		return cfg.TemperatureOffset
	}
	hcOverK := 0.014387773
	temp := hcOverK * shiftCm / lnCorr
	return temp + cfg.TemperatureOffset
}'''

new = '''func TemperatureFromRatio(ratio float64, laserNu float64, shiftCm float64, cfg *config.Config) float64 {
	if ratio <= 0 {
		return 0.0
	}
	absShift := shiftCm
	if absShift < 0 {
		absShift = -absShift
	}
	nuPlus := laserNu + absShift
	nuMinus := laserNu - absShift
	if nuPlus <= 0 || nuMinus <= 0 {
		return 0.0
	}
	freqFactor := nuMinus / nuPlus
	freqFactorPow := freqFactor * freqFactor * freqFactor * freqFactor
	correction := ratio / freqFactorPow
	if correction <= 0 {
		return 0.0
	}
	lnCorr := natLog(correction)
	if lnCorr <= 0 {
		return 0.0
	}
	return 0.014387773 * absShift / lnCorr
}'''

assert old in src, "TemperatureFromRatio function not found"
src = src.replace(old, new, 1)

with open(path, 'w') as f:
    f.write(src)
PYEOF

# Fix 4: pkg/results/report.go — use detected peak shift for raman_shift_cm, not calibration constant,
# remove referenceRatio dependency
python3 << 'PYEOF'
path = "pkg/results/report.go"
with open(path) as f:
    src = f.read()

old = '''func BuildReport(spec *models.RamanSpectrum, cfg *config.Config) *models.Report {
	stokesShift := cfg.LaserWavenumber - cfg.RamanShiftCal
	antiStokesShift := cfg.LaserWavenumber + cfg.RamanShiftCal

	stokesPeak := spectrum.DetectPeak(spec.Points, stokesShift, cfg.PeakWindowHalf, cfg.MinPeakHeight)
	antiStokesPeak := spectrum.DetectPeak(spec.Points, antiStokesShift, cfg.PeakWindowHalf, cfg.MinPeakHeight)

	ratio := analysis.ComputeRatio(stokesPeak, antiStokesPeak, cfg)
	temperature := analysis.ComputeTemperature(spec, stokesPeak, antiStokesPeak, cfg)
	peakShift := analysis.ComputePeakShift(stokesPeak, antiStokesPeak)

	expectedRatio := referenceRatio(cfg)
	residual := ratio - expectedRatio

	return &models.Report{
		Sample: models.ReportSample{
			SampleID: "raman_calib_2025_001",
			Method:   "stokes_anti_stokes_thermometry",
		},
		Parameters: models.ReportParameters{
			LaserWavenumber:   cfg.LaserWavenumber,
			RamanShiftCm:      cfg.RamanShiftCal,
			BoseModel:         cfg.BoseModel,
			FrequencyExponent: cfg.FrequencyExponent,
			TemperatureOffset: cfg.TemperatureOffset,
		},
		Summary: models.ReportSummary{
			StokesPeakCenter:      stokesPeak.Center,
			AntiStokesPeakCenter:  antiStokesPeak.Center,
			PeakShift:             peakShift,
			StokesIntensity:       stokesPeak.Height,
			AntiStokesIntensity:   antiStokesPeak.Height,
			StokesAntiStokesRatio: ratio,
			TemperatureEstimate:   temperature,
			Residual:              residual,
		},
	}
}

func referenceRatio(cfg *config.Config) float64 {
	nu0 := cfg.LaserWavenumber
	nuM := cfg.RamanShiftCal
	nuPlus := nu0 + nuM
	nuMinus := nu0 - nuM
	if nuPlus <= 0 || nuMinus <= 0 {
		return 1.0
	}
	freqFactor := nuMinus / nuPlus
	exp := cfg.FrequencyExponent
	freqFactorPow := 1.0
	for i := 0; i < int(exp); i++ {
		freqFactorPow *= freqFactor
	}
	return freqFactorPow
}'''

new = '''func BuildReport(spec *models.RamanSpectrum, cfg *config.Config) *models.Report {
	stokesShift := cfg.LaserWavenumber - cfg.RamanShiftCal
	antiStokesShift := cfg.LaserWavenumber + cfg.RamanShiftCal

	stokesPeak := spectrum.DetectPeak(spec.Points, stokesShift, cfg.PeakWindowHalf, cfg.MinPeakHeight)
	antiStokesPeak := spectrum.DetectPeak(spec.Points, antiStokesShift, cfg.PeakWindowHalf, cfg.MinPeakHeight)

	detectedShift := (stokesPeak.Center - antiStokesPeak.Center) / 2.0

	ratio := analysis.ComputeRatio(stokesPeak, antiStokesPeak, cfg)
	temperature := spectrum.TemperatureFromRatio(ratio, cfg.LaserWavenumber, detectedShift, cfg)
	peakShift := analysis.ComputePeakShift(stokesPeak, antiStokesPeak)

	return &models.Report{
		Sample: models.ReportSample{
			SampleID: "raman_calib_2025_001",
			Method:   "stokes_anti_stokes_thermometry",
		},
		Parameters: models.ReportParameters{
			LaserWavenumber:   cfg.LaserWavenumber,
			RamanShiftCm:      detectedShift,
			BoseModel:         cfg.BoseModel,
			FrequencyExponent: cfg.FrequencyExponent,
			TemperatureOffset: cfg.TemperatureOffset,
		},
		Summary: models.ReportSummary{
			StokesPeakCenter:      stokesPeak.Center,
			AntiStokesPeakCenter:  antiStokesPeak.Center,
			PeakShift:             peakShift,
			StokesIntensity:       stokesPeak.Height,
			AntiStokesIntensity:   antiStokesPeak.Height,
			StokesAntiStokesRatio: ratio,
			TemperatureEstimate:   temperature,
			Residual:              0.0,
		},
	}
}'''

assert old in src, "BuildReport + referenceRatio functions not found"
src = src.replace(old, new, 1)

with open(path, 'w') as f:
    f.write(src)
PYEOF

# Build and run
cd /app && go build -o bin/raman-temp ./cmd/raman-temp
/app/bin/raman-temp
