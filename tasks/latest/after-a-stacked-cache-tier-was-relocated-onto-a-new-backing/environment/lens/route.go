package lens

import (
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/laneio"
)

func Choose(ws string, slot int, v model.Vault, frame model.Frame) string {
	live := model.Live{
		Payload: laneio.SlowPayload(ws, slot),
		Epoch:   laneio.SlowEpoch(ws, slot),
		Slot:    slot,
	}
	cand := model.Candidate{
		Payload: laneio.FastPayload(ws, slot, v.MapRows),
		Epoch:   laneio.FastEpoch(ws, slot, v.MapRows),
		Slot:    slot,
	}
	if cand.Epoch >= live.Epoch && cand.Payload != "" {
		return cand.Payload
	}
	return live.Payload
}
