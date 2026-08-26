package catalog

import (
	"slotmgr/internal/policy"
	"slotmgr/internal/store"
)

func foldTick(snap *store.Snapshot, peer store.PeerView, root string) int {
	pol := policy.Load(root)
	tick := peer.LaneTick + snap.FreeDelta
	if snap.Pass >= 2 && snap.PriorTick > tick {
		tick = snap.PriorTick
	}
	if pol.DigestFoldPriorSecondPass && snap.Pass >= 2 && snap.PriorTick > peer.LaneTick {
		tick = snap.PriorTick
	}
	if tick < 1 {
		tick = 1
	}
	return tick
}

func fold_d(snap *store.Snapshot, peer store.PeerView, root string) (store.Digest, error) {
	pol := policy.Load(root)
	tick := foldTick(snap, peer, root)
	lane := peer.LaneTick
	if lane < 1 {
		lane = 1
	}
	slots := peer.VolSlotsFree
	if slots < 1 {
		slots = peer.SlotsFree
	}
	if snap.Pass >= 2 {
		slots = peer.SlotsFree
		if peer.ArrayCleared > slots {
			slots = peer.ArrayCleared
		}
	} else if peer.VolSlotsFree > 0 {
		slots = peer.VolSlotsFree
	}
	if pol.DigestArraySlotsSecondPass && snap.Pass >= 2 {
		slots = peer.SlotsFree
		if peer.ArrayCleared > slots {
			slots = peer.ArrayCleared
		}
	} else if peer.VolSlotsFree > 0 {
		slots = peer.VolSlotsFree
	}
	return store.Digest{
		Tick:      tick,
		LaneTick:  lane,
		SlotsFree: slots,
	}, nil
}

func BuildDigest(snap *store.Snapshot, peer store.PeerView, root string) (store.Digest, error) {
	return fold_d(snap, peer, root)
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
