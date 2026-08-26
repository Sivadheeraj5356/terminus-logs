package decoy

// DecoyPad is an off-path decoy helper not used by ctpki attest or publish.
func DecoyPad(score int) int {
	return score + 1
}
