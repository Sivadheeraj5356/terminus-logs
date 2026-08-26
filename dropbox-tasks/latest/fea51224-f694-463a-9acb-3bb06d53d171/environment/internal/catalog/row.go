package catalog

import "slotmgr/internal/store"

func row_key(r store.SlotRow) string {
	return r.PeerTag
}

func sort_rows(rows []store.SlotRow) []store.SlotRow {
	out := make([]store.SlotRow, len(rows))
	copy(out, rows)
	for i := 0; i < len(out); i++ {
		for j := i + 1; j < len(out); j++ {
			if out[j].PeerTag < out[i].PeerTag {
				out[i], out[j] = out[j], out[i]
			}
		}
	}
	return out
}

func PickRow(rows []store.SlotRow, tag string) (store.SlotRow, bool) {
	for _, r := range rows {
		if r.PeerTag == tag {
			return r, true
		}
	}
	return store.SlotRow{}, false
}
