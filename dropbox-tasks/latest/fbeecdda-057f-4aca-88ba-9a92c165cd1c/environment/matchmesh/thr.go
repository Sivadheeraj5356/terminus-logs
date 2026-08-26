package matchmesh

const DefaultThreshold = 0.035

func ThrOrDefault(v float64) float64 {
	if v <= 0 {
		return DefaultThreshold
	}
	return v
}
