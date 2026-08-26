package monitoring

func AbsFloat64(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

func MinFloat64(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func MaxFloat64(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
