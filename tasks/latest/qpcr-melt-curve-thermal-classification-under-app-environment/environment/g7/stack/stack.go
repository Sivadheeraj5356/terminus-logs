package stack

import "g7.example/attest/m7"

// StackApply applies ladder step merge through merge_hold_b.
func StackApply(pack *m7.PackState, tagA, tagB uint64, incoming [3][4]float64) [3][4]float64 {
	inc := &m7.PackState{
		LastA:   tagA,
		LastB:   tagB,
		Storage: incoming,
	}
	return m7.MergeHoldB(pack, inc, tagB)
}
