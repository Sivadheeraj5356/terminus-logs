package spine

import "sort"

// NormalizeBoundaries returns ascending, unique, strictly increasing boundaries below horizon.
func NormalizeBoundaries(boundaries []int, horizon int) []int {
	if len(boundaries) == 0 {
		return nil
	}
	seen := make(map[int]bool)
	var out []int
	for _, b := range boundaries {
		if b < 1 {
			b = 1
		}
		if b > horizon {
			b = horizon
		}
		if seen[b] {
			continue
		}
		seen[b] = true
		out = append(out, b)
	}
	sort.Ints(out)
	if len(out) == 0 {
		return out
	}
	compact := []int{out[0]}
	for i := 1; i < len(out); i++ {
		if out[i] > compact[len(compact)-1] {
			compact = append(compact, out[i])
		}
	}
	return compact
}
