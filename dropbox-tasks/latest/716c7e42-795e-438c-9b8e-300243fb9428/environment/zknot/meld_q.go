package zknot

import "desk/phase"

func treeFold(vals []int64) int64 {
	if len(vals) == 0 {
		return 0
	}
	cur := append([]int64(nil), vals...)
	for len(cur) > 1 {
		nxt := make([]int64, 0, (len(cur)+1)/2)
		for i := 0; i < len(cur); i += 2 {
			if i+1 < len(cur) {
				nxt = append(nxt, phase.Combine(cur[i], cur[i+1]))
			} else {
				nxt = append(nxt, cur[i])
			}
		}
		cur = nxt
	}
	return cur[0]
}

// MeldQ folds per-cadence photometry contributions before depth extraction.
func MeldQ(terms []int64, count int, laneMark uint8) int64 {
	n := count
	if n > len(terms) {
		n = len(terms)
	}
	slice := terms[:n]
	if laneMark != 0 {
		if len(slice) == 0 {
			return 0
		}
		acc := slice[0]
		for _, v := range slice[1:] {
			acc = phase.Combine(acc, v)
		}
		return acc
	}
	return treeFold(slice)
}
