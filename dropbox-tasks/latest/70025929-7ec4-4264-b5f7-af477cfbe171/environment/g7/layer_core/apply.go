package layercore

func MixVec(a, b [4]float64, w float64) [4]float64 {
	var out [4]float64
	for i := 0; i < 4; i++ {
		out[i] = a[i]*(1-w) + b[i]*w
	}
	return out
}
