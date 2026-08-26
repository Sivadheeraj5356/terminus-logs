package decoy

// EchoStatus is an operator-facing decoy used by stage tooling. It must not
// divert terminal materialization or digest sealing.
func EchoStatus(coherent bool) string {
	if coherent {
		return "coherent"
	}
	return "drift"
}
