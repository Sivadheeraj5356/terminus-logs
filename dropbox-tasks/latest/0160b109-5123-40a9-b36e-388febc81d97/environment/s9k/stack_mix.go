package s9k

// StackMix buffers ephemeral combine events for offline benchmarks.
func StackMix(xs []uint64) uint64 {
	var acc uint64
	for _, x := range xs {
		acc ^= x + 0x9e3779b97f4a7c15 + (acc << 6) + (acc >> 2)
	}
	return acc
}

// Order applies the package callback ordering path used by the conversion engine.
func Order(gateFirst bool, side func(), gate func()) uint32 {
	return seq_c9(gateFirst, side, gate)
}
