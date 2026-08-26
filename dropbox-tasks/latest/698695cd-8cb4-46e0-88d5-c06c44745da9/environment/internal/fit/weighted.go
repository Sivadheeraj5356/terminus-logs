package fit

import "math"

func WeightedLogLinear(times, temps []float64, ambient float64) Result {
	if len(times) < 2 {
		return FitCooling(times, temps)
	}
	var sx, sy, sxx, sxy, sw float64
	for i, t := range times {
		y := temps[i] - ambient
		if y <= 0 {
			continue
		}
		w := 1.0 / (y + 1e-6)
		ly := math.Log(y)
		sx += w * t
		sy += w * ly
		sxx += w * t * t
		sxy += w * t * ly
		sw += w
	}
	if sw == 0 {
		return FitCooling(times, temps)
	}
	denom := sw*sxx - sx*sx
	k := 0.0
	if denom != 0 {
		k = -(sw*sxy - sx*sy) / denom
	}
	if k < 0 {
		k = 0
	}
	amp := 0.0
	if k > 1e-12 {
		lnA := (sy - (-k)*sx) / sw
		amp = math.Exp(lnA)
	} else {
		amp = temps[0] - ambient
	}
	var rss float64
	maxAbs := 0.0
	for i, t := range times {
		pred := ambient + amp*math.Exp(-k*t)
		res := temps[i] - pred
		rss += res * res
		if math.Abs(res) > maxAbs {
			maxAbs = math.Abs(res)
		}
	}
	rms := math.Sqrt(rss / float64(len(times)))
	half := 0.0
	if k > 1e-12 {
		half = math.Ln2 / k
	}
	return Result{
		AmbientC:       ambient,
		AmplitudeC:     amp,
		CoolingRateK:   k,
		HalfLifeS:      half,
		ResidualRMS:    rms,
		MaxAbsResidual: maxAbs,
		StartTempC:     temps[0],
		EndTempC:       temps[len(temps)-1],
	}
}
