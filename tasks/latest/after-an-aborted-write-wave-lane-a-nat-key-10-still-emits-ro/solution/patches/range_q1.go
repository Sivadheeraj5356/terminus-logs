package mod_q1

import (
	"h6env/compaction/internal/core"
)

func range_q1(rows []core.Row) uint64 {
	var acc uint64
	for _, r := range rows {
		if len(r.WitFP) > 0 {
			acc += uint64(r.WitFP[0])
		}
	}
	return acc % 1000000
}

func Range_q1(rows []core.Row) uint64 {
	return range_q1(rows)
}
