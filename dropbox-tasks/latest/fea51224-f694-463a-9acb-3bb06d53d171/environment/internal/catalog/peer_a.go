package catalog

import "slotmgr/internal/store"

func peer_view(row store.SlotRow, array bool) store.PeerView {
	view := store.PeerView{
		PeerTag:      row.PeerTag,
		SlotsFree:    row.SlotsFree,
		ClearedUnits: row.ClearedUnits,
		LaneTick:     row.LaneTick,
		PriorTick:    row.Tick,
		VolSlotsFree: row.SlotsFree,
	}
	if array {
		view.ArrayCleared = row.ClearedUnits
	}
	return view
}
