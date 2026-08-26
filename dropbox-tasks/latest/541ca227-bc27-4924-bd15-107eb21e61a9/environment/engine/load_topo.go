package engine

func PermuteProfileNames(seed int, names []string) []string {
	if len(names) <= 1 {
		out := make([]string, len(names))
		copy(out, names)
		return out
	}
	out := make([]string, len(names))
	copy(out, names)
	for i := len(out) - 1; i > 0; i-- {
		seed = (1103515245*seed + 12345) & 0x7fffffff
		j := seed % (i + 1)
		out[i], out[j] = out[j], out[i]
	}
	return out
}
