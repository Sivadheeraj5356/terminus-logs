package p2_pick

func PickShare(picks int, rosterSize int) float64 {
	if rosterSize <= 0 {
		return 0
	}
	return float64(picks) / float64(rosterSize)
}
