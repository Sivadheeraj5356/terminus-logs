package weave

import (
	"jwksbound.local/mux/vault"
	"jwksbound.local/mux/quorum"
	"jwksbound.local/mux/model"
)

// RunPhase builds the reconciled view for one profile run and phase.
func RunPhase(profile model.ProfileSpec, runID, phaseName string, epochVal int) model.ViewState {
	ctx := model.Context{Profile: profile.Name, Epoch: epochVal, Phase: phaseName, RunID: runID}
	records := vault.LoadPrimary(profile.Name)
	floor := quorum.Floor(profile.Name)
	records = quorum.Active(records, floor)
	segments := vault.SelectSegment(records, ctx)
	state := model.ViewState{Phase: phaseName, RunID: runID}
	if phaseName == "settle" {
		state = ReconcilePhase(state, segments)
		applyCtx := model.Context{Profile: profile.Name, Epoch: epochVal, Phase: "apply", RunID: runID}
		applySeg := vault.SelectSegment(records, applyCtx)
		state = ReconcilePhase(state, applySeg)
		return state
	}
	if idx := runIndex(profile.Runs, runID); idx > 0 {
		prev := profile.Runs[idx-1]
		prevState := RunPhase(profile, prev, "settle", epochVal)
		carry := CarryFromSettle(prevState)
		for _, e := range carry {
			state.Entries = append(state.Entries, e)
		}
	}
	return ReconcilePhase(state, segments)
}

func runIndex(runs []string, runID string) int {
	for i, id := range runs {
		if id == runID {
			return i
		}
	}
	return -1
}
