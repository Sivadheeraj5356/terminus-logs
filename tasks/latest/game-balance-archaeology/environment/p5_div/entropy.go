package p5_div

func NormEntropy(shares []float64) float64 {
	if len(shares) == 0 {
		return 0
	}
	max := 0.0
	for _, s := range shares {
		if s > max {
			max = s
		}
	}
	if max <= 0 {
		return 0
	}
	return 1.0 / max
}
