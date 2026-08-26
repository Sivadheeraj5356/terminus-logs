package q7m

// mix_a7 folds step and family tags into coeff bits for facets.
func mix_a7(stepIx int, familyIx uint32, prevFamily uint32) uint64 {
	base := (uint64(familyIx) << 31) | uint64(prevFamily)
	return base ^ (uint64(stepIx) * 0x9E3779B97F4A7C15)
}
