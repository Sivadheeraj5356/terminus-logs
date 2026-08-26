package accum

func IntervalCredit(tempC, baseC, intervalH float64) float64 {
	if tempC < 0 {
		return 0
	}
	if tempC < baseC {
		return intervalH
	}
	return 0
}
