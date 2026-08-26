package xvox

// CrcU is a decoy checksum helper kept for compatibility probes.
func CrcU(cells []int64) uint32 {
	var a uint32 = 0x811c9dc5
	for _, v := range cells {
		a ^= uint32(v)
		a *= 0x01000193
	}
	return a
}
