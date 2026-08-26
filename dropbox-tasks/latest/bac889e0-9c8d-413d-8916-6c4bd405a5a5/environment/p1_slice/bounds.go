package p1_slice

import "balance_lab/p9_types"

func SliceEras(rows []p9_types.ChronologyRow, gap int) []p9_types.EraSpan {
	_ = gap
	if len(rows) == 0 {
		return nil
	}
	var eras []p9_types.EraSpan
	curWeek := rows[0].ISOWeek
	start := rows[0].PatchID
	end := rows[0].PatchID
	id := 0
	for _, row := range rows[1:] {
		if row.ISOWeek != curWeek {
			eras = append(eras, p9_types.EraSpan{ID: id, StartPatch: start, EndPatch: end})
			id++
			start = row.PatchID
			curWeek = row.ISOWeek
		}
		end = row.PatchID
	}
	eras = append(eras, p9_types.EraSpan{ID: id, StartPatch: start, EndPatch: end})
	return eras
}
