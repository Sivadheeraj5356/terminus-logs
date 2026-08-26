package spectrum

import (
	"encoding/json"
	"os"

	"github.com/spectro/raman-temp/pkg/config"
	"github.com/spectro/raman-temp/pkg/models"
)

func LoadSpectrum(path string) (*models.RamanSpectrum, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var spec models.RamanSpectrum
	if err := json.Unmarshal(data, &spec); err != nil {
		return nil, err
	}
	return &spec, nil
}

func DetectPeak(points []models.SpectrumPoint, centerGuess float64, halfWindow float64, minHeight float64) models.Peak {
	var peakPoints []models.SpectrumPoint
	for _, p := range points {
		if p.Wavenumber >= centerGuess-halfWindow && p.Wavenumber <= centerGuess+halfWindow {
			peakPoints = append(peakPoints, p)
		}
	}
	if len(peakPoints) == 0 {
		return models.Peak{Center: centerGuess, Height: 0, Width: 0, Area: 0}
	}
	maxIdx := 0
	maxIntensity := peakPoints[0].Intensity
	for i, p := range peakPoints {
		if p.Intensity > maxIntensity {
			maxIntensity = p.Intensity
			maxIdx = i
		}
	}
	if maxIntensity < minHeight {
		return models.Peak{Center: centerGuess, Height: maxIntensity, Width: 0, Area: 0}
	}
	center := peakPoints[maxIdx].Wavenumber

	var halfMaxLeft, halfMaxRight float64
	halfMax := maxIntensity / 2
	leftIdx := maxIdx
	for leftIdx > 0 && peakPoints[leftIdx].Intensity > halfMax {
		leftIdx--
	}
	rightIdx := maxIdx
	for rightIdx < len(peakPoints)-1 && peakPoints[rightIdx].Intensity > halfMax {
		rightIdx++
	}
	halfMaxLeft = peakPoints[leftIdx].Wavenumber
	halfMaxRight = peakPoints[rightIdx].Wavenumber
	width := halfMaxRight - halfMaxLeft

	var area float64
	for i := 1; i < len(peakPoints); i++ {
		dx := peakPoints[i].Wavenumber - peakPoints[i-1].Wavenumber
		avgIntensity := (peakPoints[i].Intensity + peakPoints[i-1].Intensity) / 2
		area += avgIntensity * dx
	}

	return models.Peak{
		Center: center,
		Height: maxIntensity,
		Width:  width,
		Area:   area,
	}
}

func ComputeBoseFactor(wavenumberCm float64, temperatureK float64, cfg *config.Config) float64 {
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
}

func expApprox(x float64) float64 {
	if x < -700 {
		return 0
	}
	if x > 700 {
		return 1.0e300
	}
	result := 1.0
	term := 1.0
	for i := 1; i <= 60; i++ {
		term *= x / float64(i)
		result += term
	}
	return result
}

func TemperatureFromRatio(ratio float64, laserNu float64, shiftCm float64, cfg *config.Config) float64 {
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
}

func natLog(x float64) float64 {
	if x <= 0 {
		return 0
	}
	y := (x - 1) / (x + 1)
	y2 := y * y
	result := 0.0
	term := y
	for i := 1; i <= 100; i += 2 {
		result += term / float64(i)
		term *= y2
	}
	return 2 * result
}
