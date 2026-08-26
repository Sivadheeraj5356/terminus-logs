package weave

import "jwksbound.local/mux/model"

// CarryFromSettle selects the settle-view entries that carry into the next run.
func CarryFromSettle(state model.ViewState) map[string]model.Entry {
	out := map[string]model.Entry{}
	for _, e := range state.Entries {
		if e.Mark > model.CarryMark {
			out[e.Key] = e
		}
	}
	return out
}
