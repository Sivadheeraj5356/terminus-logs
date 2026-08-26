package m5

func widenStamp(x uint64, shift uint) uint64 {
	return x ^ (x >> shift)
}

func bodyMix(a, b uint32) uint64 {
	return (uint64(a) << 16) | uint64(b)
}
