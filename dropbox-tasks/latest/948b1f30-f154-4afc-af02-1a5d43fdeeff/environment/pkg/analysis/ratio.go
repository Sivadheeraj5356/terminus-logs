package analysis

import (
	"github.com/spectro/raman-temp/pkg/config"
	"github.com/spectro/raman-temp/pkg/models"
	"github.com/spectro/raman-temp/pkg/spectrum"
)

func ComputeRatio(stokesPeak, antiStokesPeak models.Peak, cfg *config.Config) float64 {
	if antiStokesPeak.Height <= 0 {
		return 0
	}
	if cfg.RatioConvention == "anti_over_stokes" {
		return antiStokesPeak.Height / stokesPeak.Height
	}
	return stokesPeak.Height / antiStokesPeak.Height
}

func ComputeTemperature(spec *models.RamanSpectrum, stokesPeak, antiStokesPeak models.Peak, cfg *config.Config) float64 {
	ratio := ComputeRatio(stokesPeak, antiStokesPeak, cfg)
	return spectrum.TemperatureFromRatio(ratio, cfg.LaserWavenumber, cfg.RamanShiftCal, cfg)
}

func ComputePeakShift(stokesPeak, antiStokesPeak models.Peak) float64 {
	return (stokesPeak.Center - antiStokesPeak.Center) / 2.0
}
