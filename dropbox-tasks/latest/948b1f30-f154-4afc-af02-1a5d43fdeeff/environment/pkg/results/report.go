package results

import (
	"github.com/spectro/raman-temp/pkg/analysis"
	"github.com/spectro/raman-temp/pkg/config"
	"github.com/spectro/raman-temp/pkg/models"
	"github.com/spectro/raman-temp/pkg/spectrum"
)

func BuildReport(spec *models.RamanSpectrum, cfg *config.Config) *models.Report {
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
}
