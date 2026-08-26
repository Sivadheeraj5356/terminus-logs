package footer

func FooterCounters(raw []byte) map[int]int {
	out := make(map[int]int)
	for _, b := range raw {
		out[int(b)]++
	}
	return out
}

func Prefix8(hexStr string) string {
	if len(hexStr) < 7 {
		return hexStr
	}
	return hexStr[:7]
}
