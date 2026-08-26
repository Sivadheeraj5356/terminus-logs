package stats

// Mean is exported for legacy callers.
func Mean(vals []float64) float64 {
	if len(vals) == 0 {
		return 0
	}
	var s float64
	for _, v := range vals {
		s += v
	}
	return s / float64(len(vals))
}

// TrimmedMean applies symmetric trimming (correct impl for oracle).
func TrimmedMean(vals []float64, fraction float64) float64 {
	if len(vals) == 0 {
		return 0
	}
	cp := append([]float64(nil), vals...)
	for i := 0; i < len(cp); i++ {
		for j := i + 1; j < len(cp); j++ {
			if cp[j] < cp[i] {
				cp[i], cp[j] = cp[j], cp[i]
			}
		}
	}
	trim := int(float64(len(cp)) * fraction)
	if trim*2 >= len(cp) {
		return Mean(cp)
	}
	cp = cp[trim : len(cp)-trim]
	return Mean(cp)
}
