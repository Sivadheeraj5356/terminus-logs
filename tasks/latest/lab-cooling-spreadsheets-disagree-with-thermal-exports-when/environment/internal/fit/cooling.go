package fit

import "math"

type Result struct {
	AmbientC      float64
	AmplitudeC    float64
	CoolingRateK  float64
	HalfLifeS     float64
	ResidualRMS   float64
	MaxAbsResidual float64
	StartTempC    float64
	EndTempC      float64
}

func FitCooling(times, temps []float64) Result {
	if len(times) == 0 {
		return Result{}
	}
	ambient := temps[len(temps)-1]
	var sx, sy, sxx, sxy float64
	n := float64(len(times))
	for i := range times {
		sx += times[i]
		sy += temps[i]
		sxx += times[i] * times[i]
		sxy += times[i] * temps[i]
	}
	denom := n*sxx - sx*sx
	slope := 0.0
	if denom != 0 {
		slope = (n*sxy - sx*sy) / denom
	}
	intercept := (sy - slope*sx) / n
	var rss float64
	maxAbs := 0.0
	for i := range times {
		pred := intercept + slope*times[i]
		res := temps[i] - pred
		rss += res * res
		if math.Abs(res) > maxAbs {
			maxAbs = math.Abs(res)
		}
	}
	rms := 0.0
	if len(times) > 0 {
		rms = math.Sqrt(rss / float64(len(times)))
	}
	return Result{
		AmbientC:       ambient,
		AmplitudeC:     intercept - ambient,
		CoolingRateK:   -slope,
		HalfLifeS:      0,
		ResidualRMS:    rms,
		MaxAbsResidual: maxAbs,
		StartTempC:     temps[0],
		EndTempC:       temps[len(temps)-1],
	}
}
