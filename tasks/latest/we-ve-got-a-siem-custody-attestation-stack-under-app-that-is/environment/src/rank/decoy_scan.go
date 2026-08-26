package rank

func RankScan(values []int) []int {
	out := make([]int, len(values))
	copy(out, values)
	for i := 0; i < len(out); i++ {
		for j := i + 1; j < len(out); j++ {
			if out[j] < out[i] {
				out[i], out[j] = out[j], out[i]
			}
		}
	}
	return out
}

func RankPeak(values []int) int {
	if len(values) == 0 {
		return 0
	}
	peak := values[0]
	for _, v := range values[1:] {
		if v > peak {
			peak = v
		}
	}
	return peak
}
