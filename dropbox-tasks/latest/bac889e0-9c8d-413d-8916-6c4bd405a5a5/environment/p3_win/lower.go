package p3_win

func WinLower(wins, picks int, z float64) float64 {
	if picks <= 0 {
		return 0
	}
	return float64(wins) / float64(picks)
}
