package m7

import (
	"fmt"
	"math"
)

func Classify(measured, uplink, tolerance float64, stress bool) (string, float64, error) {
	if math.IsNaN(measured) || math.IsInf(measured, 0) ||
		math.IsNaN(uplink) || math.IsInf(uplink, 0) ||
		math.IsNaN(tolerance) || math.IsInf(tolerance, 0) || tolerance <= 0 {
		return "", 0, fmt.Errorf("invalid thermal values")
	}
	delta := measured - uplink
	if stress {
		if math.Abs(delta) <= tolerance {
			return "within", tolerance, nil
		}
		if delta > 0 {
			return "over", tolerance, nil
		}
		return "within", tolerance, nil
	}
	if math.Abs(delta) <= tolerance {
		return "within", tolerance, nil
	}
	return "outside", tolerance, nil
}
