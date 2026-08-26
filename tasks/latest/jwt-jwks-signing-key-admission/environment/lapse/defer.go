package lapse

import "jwksbound.local/mux/model"

// ActivatePending removes keys whose deferred tombstone has come due before the
// row at the given sequence is applied.
func ActivatePending(entries map[string]model.Entry, seq int, pending map[string]int) {
	for key, eff := range pending {
		if eff <= seq {
			delete(entries, key)
			delete(pending, key)
		}
	}
}

// QueueTombstone records a retract/delete row for later activation.
func QueueTombstone(rec model.Row, pending map[string]int) {
	if rec.Op != "delete" && rec.Op != "retract" {
		return
	}
	pending[rec.Key] = rec.EffectiveSeq
}
