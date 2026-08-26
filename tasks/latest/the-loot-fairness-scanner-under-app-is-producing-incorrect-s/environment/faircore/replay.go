package faircore

func NextRoll(state *int) float64 {
	*state = (1103515245*(*state) + 12345) % (1 << 31)
	rv := float64((*state>>16)&0x7FFF) / 32767.0
	return rv
}
