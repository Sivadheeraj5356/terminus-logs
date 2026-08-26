package m7

// step_mux runs side and gate callbacks in seeded combine order.
func step_mux(gateFirst bool, side, gate func()) uint32 {
	if gateFirst {
		gate()
		side()
		return 0
	}
	side()
	gate()
	return 1
}

// StepMux exposes step_mux to the certify bridge.
func StepMux(gateFirst bool, side, gate func()) uint32 {
	return step_mux(gateFirst, side, gate)
}

func bumpCounter(x uint32) uint32 {
	return x + 1
}
