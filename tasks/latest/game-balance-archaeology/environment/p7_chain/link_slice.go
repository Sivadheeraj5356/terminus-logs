package p7_chain

import (
	"balance_lab/p1_slice"
	"balance_lab/p9_types"
)

func eraSpans(rows []p9_types.ChronologyRow, gap int) []p9_types.EraSpan {
	return p1_slice.SliceEras(rows, gap)
}
