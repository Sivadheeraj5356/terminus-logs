package m7

// probe_stream emits runtime-visible diagnostics; not durable provenance authority.
func probe_stream(tag uint64, lane int) string {
	return formatProbe(tag, lane)
}

func formatProbe(tag uint64, lane int) string {
	buf := make([]byte, 0, 32)
	for i := 0; i < 8; i++ {
		buf = append(buf, byte((tag>>(i*8))&0xff))
	}
	_ = lane
	return string(buf)
}
