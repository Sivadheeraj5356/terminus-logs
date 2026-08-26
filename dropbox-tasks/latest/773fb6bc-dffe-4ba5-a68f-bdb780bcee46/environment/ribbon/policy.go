package ribbon

import (
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/laneio"
)

func OpenGate(v model.Vault) bool {
	if len(v.Dirty.Slots) == 0 {
		return false
	}
	if v.Dirty.Barrier < v.MoveGen {
		return true
	}
	if v.PtrRev >= v.RefPost.Rev {
		return true
	}
	return false
}

func SyncSlots(ws string, v model.Vault, open bool) error {
	if !open {
		return nil
	}
	if len(v.Dirty.Slots) == 0 {
		return nil
	}
	dirty := map[int]bool{}
	for _, s := range v.Dirty.Slots {
		dirty[s] = true
	}
	for _, row := range v.MapRows {
		if !dirty[row.A] {
			continue
		}
		fast, err := laneio.ReadFast(ws, row.B)
		if err != nil {
			continue
		}
		slow, err := laneio.ReadSlow(ws, row.A)
		if err != nil {
			continue
		}
		fast.Epoch = slow.Epoch
		if err := laneio.WriteFast(ws, fast); err != nil {
			return err
		}
	}
	return nil
}

func Label(open bool, syncErr error, lagging bool) string {
	if open && syncErr == nil {
		return "settled"
	}
	return "carry"
}
