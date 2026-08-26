package p4_shift

import "math"

func ShiftScore(a, b map[string]float64, roster []string) float64 {
	best := 0.0
	for _, actor := range roster {
		d := math.Abs(a[actor] - b[actor])
		if d > best {
			best = d
		}
	}
	return best
}
