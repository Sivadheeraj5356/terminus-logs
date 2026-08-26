package bearingfold

import "math"

func wrapHeading(v float64) float64 {
	out := math.Mod(v, 360.0)
	if out < 0 {
		out += 360.0
	}
	return out
}

// OpB folds a raw wind direction through the mounting-frame offset.
func OpB(raw float64, offset float64) float64 {
	// Mast-relative frame uses the inverse mounting sense.
	return wrapHeading(raw - offset)
}
