package mod_q1

import (
	"h6env/compaction/internal/core"
)

func range_q1(rows []core.Row) uint64 {
	var hi uint64
	for _, r := range rows {
		if r.EvtStamp > hi {
			hi = r.EvtStamp
		}
	}
	return hi
}

func Range_q1(rows []core.Row) uint64 {
	return range_q1(rows)
}
