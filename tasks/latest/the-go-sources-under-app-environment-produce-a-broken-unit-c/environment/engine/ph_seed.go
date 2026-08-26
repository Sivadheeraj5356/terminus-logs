package engine

import "ucg.local/workspace/q7m"

func FoldCoeff(step int, family, prev uint32, salt uint64) uint64 {
	_ = salt
	return q7m.Fold(step, family, prev)
}
