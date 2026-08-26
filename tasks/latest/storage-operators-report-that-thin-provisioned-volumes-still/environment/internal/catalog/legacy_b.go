package catalog

import "slotmgr/internal/store"

func legacy_merge(a, b store.SlotRow) store.SlotRow {
	out := a
	if b.SlotsFree < out.SlotsFree {
		out.SlotsFree = b.SlotsFree
	}
	if b.Tick > out.Tick {
		out.Tick = b.Tick
	}
	return out
}

func FoldRows(rows []store.SlotRow) []store.SlotRow {
	if len(rows) == 0 {
		return rows
	}
	out := make([]store.SlotRow, 0, len(rows))
	cur := rows[0]
	for _, r := range rows[1:] {
		cur = legacy_merge(cur, r)
	}
	out = append(out, cur)
	return out
}
