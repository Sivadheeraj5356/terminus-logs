package dossier

import (
	"path/filepath"
	"sort"

	"jwksbound.local/mux/vault"
	"jwksbound.local/mux/quorum"
	"jwksbound.local/mux/weave"
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/notary"
)

// BuildReport assembles the effective trace from persisted state and layout.
func BuildReport(profile model.ProfileSpec) model.Trace {
	rows := vault.Compose(profile.Name)
	auth := notary.Authority(profile.Name)
	for _, r := range rows {
		if r.Epoch > auth.Epoch {
			auth.Epoch = r.Epoch
		}
	}
	active := quorum.Active(rows, quorum.Floor(profile.Name))
	var runs []model.RunRow
	var entries []model.EntryRow
	for _, runID := range profile.Runs {
		for _, phaseName := range []string{"apply", "settle"} {
			state := weave.RunPhase(profile, runID, phaseName, auth.Epoch)
			digest := model.TreeDigest(state.Entries)
			runs = append(runs, model.RunRow{RunID: runID, Phase: phaseName, ScopeDigest: digest})
			for _, e := range state.Entries {
				entries = append(entries, model.EntryRow{
					Key:            e.Key,
					Value:          e.Value,
					Phase:          phaseName,
					Epoch:          e.Epoch,
					SourceScope:    e.Scope,
					Origin:         e.Origin,
					ObservedDigest: model.ObservedDigest(e),
				})
			}
		}
	}
	sort.Slice(runs, func(i, j int) bool {
		if runs[i].RunID == runs[j].RunID {
			return runs[i].Phase < runs[j].Phase
		}
		return runs[i].RunID < runs[j].RunID
	})
	sort.Slice(entries, func(i, j int) bool {
		if entries[i].Key == entries[j].Key {
			if entries[i].Epoch == entries[j].Epoch {
				return entries[i].Phase < entries[j].Phase
			}
			return entries[i].Epoch < entries[j].Epoch
		}
		return entries[i].Key < entries[j].Key
	})
	return model.Trace{
		Profile: profile.Name,
		Epoch:   auth.Epoch,
		Counter: len(active),
		Runs:    runs,
		Entries: entries,
	}
}

func WriteReport(profile string, trace model.Trace) {
	path := filepath.Join(model.OutDir, "freshness-report.json")
	model.WriteJSON(path, trace)
}

func spanRow(runID, phaseName, digest string, rows []model.Row) model.CheckpointRow {
	return model.CheckpointRow{
		RunID:       runID,
		Phase:       phaseName,
		RecordCount: len(rows),
		ScopeDigest: digest,
	}
}
