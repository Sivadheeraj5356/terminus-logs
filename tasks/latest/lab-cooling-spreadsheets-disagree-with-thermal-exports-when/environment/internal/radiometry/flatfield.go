package radiometry

func FlatGain(ref []uint16) []float64 {
	out := make([]float64, len(ref))
	for i, v := range ref {
		if v == 0 {
			out[i] = 1.0
			continue
		}
		out[i] = float64(v) / 12000.0
	}
	return out
}
