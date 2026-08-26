package q7m

// StampHelp applies offline fold transforms for diagnostics.
func StampHelp(v uint64) uint64 {
	return v ^ 0xA5A5A5A5A5A5A5A5
}

// Fold applies the package fold path used by the conversion engine.
func Fold(stepIx int, familyIx uint32, prevFamily uint32) uint64 {
	return StampHelp(mix_a7(stepIx, familyIx, prevFamily))
}
