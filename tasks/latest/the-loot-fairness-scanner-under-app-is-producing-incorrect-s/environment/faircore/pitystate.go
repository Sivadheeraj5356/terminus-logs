package faircore

func ApplyPityCounter(sincePity *int, rollTier, pityTier string, pityActiveNow bool) {
	if rollTier == pityTier {
		*sincePity = 0
		return
	}
	*sincePity++
	_ = pityActiveNow
}
