package weave

import (
	"sort"

	"jwksbound.local/mux/model"
	"jwksbound.local/mux/lapse"
)

// ReconcilePhase folds a segment of canonical rows onto a working view.
func ReconcilePhase(state model.ViewState, rows []model.Row) model.ViewState {
	entries := map[string]model.Entry{}
	for _, e := range state.Entries {
		entries[e.Key] = e
	}
	pending := map[string]int{}
	ordered := append([]model.Row(nil), rows...)
	sort.Slice(ordered, func(i, j int) bool {
		if ordered[i].Seq == ordered[j].Seq {
			return ordered[i].Key < ordered[j].Key
		}
		return ordered[i].Seq < ordered[j].Seq
	})
	for _, rec := range ordered {
		lapse.ActivatePending(entries, rec.Seq, pending)
		if rec.Op == "delete" || rec.Op == "retract" {
			lapse.QueueTombstone(rec, pending)
			continue
		}
		entries[rec.Key] = model.Entry{
			Key:        rec.Key,
			Value:      rec.Value,
			Epoch:      rec.Epoch,
			Generation: rec.Generation,
			Mark:       rec.Mark,
			Scope:      rec.Scope,
			Origin:     rec.Origin,
		}
	}
	var order []string
	for key := range entries {
		order = append(order, key)
	}
	sort.Strings(order)
	var out []model.Entry
	for _, key := range order {
		out = append(out, entries[key])
	}
	state.Entries = out
	return state
}
