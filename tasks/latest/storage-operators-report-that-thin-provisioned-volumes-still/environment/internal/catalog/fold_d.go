package catalog

import "slotmgr/internal/store"

func fold_d(snap *store.Snapshot, peer store.PeerView) (store.Digest, error) {
	tick := peer.ArrayCleared
	if tick < 1 {
		tick = 1
	}
	lane := peer.LaneTick
	if lane < 1 {
		lane = 1
	}
	return store.Digest{
		Tick:      tick,
		LaneTick:  lane,
		SlotsFree: peer.SlotsFree,
	}, nil
}

func BuildDigest(snap *store.Snapshot, peer store.PeerView) (store.Digest, error) {
	return fold_d(snap, peer)
}

func PeerView(row store.SlotRow, array bool) store.PeerView {
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
