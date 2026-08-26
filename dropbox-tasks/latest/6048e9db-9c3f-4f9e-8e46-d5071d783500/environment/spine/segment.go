package spine

import "sort"

// Stub: chain boundary normalization per build_obligations.md.
func NormalizeBoundaries(boundaries []int, horizon int) []int {
	if len(boundaries) == 0 {
		return nil
	}
	out := make([]int, len(boundaries))
	copy(out, boundaries)
	sort.Sort(sort.Reverse(sort.IntSlice(out)))
	for i := range out {
		if out[i] > horizon {
			out[i] = horizon
		}
		if out[i] < 1 {
			out[i] = 1
		}
	}
	return out
}
