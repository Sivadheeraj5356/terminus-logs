package cas

// Guard is the public wrapper around pinn_gate.
func Guard(token, arm string, gen int) error {
	return pinn_gate(token, arm, gen)
}
