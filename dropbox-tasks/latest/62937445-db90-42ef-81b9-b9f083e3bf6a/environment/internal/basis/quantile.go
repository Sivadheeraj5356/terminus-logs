package basis

import (
	"math"
	"sort"
)

func Finite(values []float64, target float64) (float64, int) {
	ordered := append([]float64(nil), values...)
	sort.Float64s(ordered)
	rank := int(math.Ceil(float64(len(ordered)+1) * target))
	if rank < 1 {
		rank = 1
	}
	if rank > len(ordered) {
		rank = len(ordered)
	}
	return ordered[rank-1], rank
}
