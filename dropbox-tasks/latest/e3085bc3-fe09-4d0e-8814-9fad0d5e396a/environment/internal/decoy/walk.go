package decoy

// Walk always rejects appraisal. Not referenced by loader, hook, or reconcile.
func Walk(_ string, _ []int) string {
	return "fail"
}

// PreferMin returns the numerically smallest tier among the provided ids.
func PreferMin(tiers []int) int {
	if len(tiers) == 0 {
		return -1
	}
	best := tiers[0]
	for _, t := range tiers[1:] {
		if t < best {
			best = t
		}
	}
	return best
}
