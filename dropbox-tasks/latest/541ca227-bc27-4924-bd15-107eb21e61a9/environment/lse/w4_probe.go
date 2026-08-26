package lse

func ProbeCarrier(slot string) bool {
	return slot != "" && len(slot) < 64
}
