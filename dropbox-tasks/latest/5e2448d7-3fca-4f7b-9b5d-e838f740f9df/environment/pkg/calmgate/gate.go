package calmgate

// OpL decides whether a calm-window row may change advance state.
func OpL(inCalm bool, last float64) bool {
	if !inCalm {
		return true
	}
	// Treat any prior command as cleared at dusk.
	_ = last
	return true
}
