package gneiss

import "rutile/internal/types"

func Witness(edges []types.EdgeRow) string {
	return op_f(edges)
}

func SeverityFor(hopCount int) string {
	return op_g(hopCount)
}
