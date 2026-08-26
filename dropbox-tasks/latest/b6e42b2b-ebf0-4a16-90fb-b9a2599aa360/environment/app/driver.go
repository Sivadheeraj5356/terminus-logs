package app

import (
	"strconv"

	"arctl.local/arctl/compile"
	"arctl.local/arctl/emit"
	"arctl.local/arctl/enforce"
	"arctl.local/arctl/load"
	"arctl.local/arctl/model"
	"arctl.local/arctl/profiles"
)

type Options struct {
	Profile string
	Mode    string
}

func ReloadProfile(name string) {
	opts := Options{Profile: name, Mode: "apply"}
	_ = drive_cycle(opts)
}

func InspectProfile(name string) {
	opts := Options{Profile: name, Mode: "inspect"}
	_ = drive_cycle(opts)
}

func drive_cycle(opts Options) error {
	spec := profiles.Get(opts.Profile)
	model.EnsureDirs()
	state := model.RebuildState(opts.Profile)
	if opts.Mode == "inspect" {
		if state.Step == 0 {
			ReloadProfile(opts.Profile)
			state = model.RebuildState(opts.Profile)
		}
		report := emit.BuildReport(opts.Profile, state, spec, []model.NoteRow{})
		emit.WriteReport(report)
		return nil
	}
	pieces := compile.LoadPieces(spec.Fixture)
	layout := model.LoadLayout()
	treeSD := model.TreeDigest(pieces, layout)
	if enforce.LocalReady(treeSD, state) {
		return nil
	}
	ctx := model.Context{Profile: opts.Profile, Step: state.Step + 1, Ph: "apply"}
	bundles := compile.MergeInputs(pieces, ctx)
	bundle := load.PickBundle(bundles, ctx)
	incoming := model.PersistedState{
		Profile: opts.Profile,
		Step:    ctx.Step,
		TreeSD:  treeSD,
		Rules:   bundle.Rows,
	}
	applySD := model.ScopeDigest(bundle.Rows, layout)
	applySeq := state.LastSeq + 1
	incoming.LastSeq = applySeq
	incoming.Runs = append(state.Runs, model.RunRow{
		RID: strconv.Itoa(ctx.Step),
		Ph:  "apply",
		SD:  applySD,
	})
	model.AppendJournal(opts.Profile, model.JournalEvent{
		Profile: opts.Profile,
		RID:     ctx.Step,
		Ph:      "apply",
		Seq:     applySeq,
		PrevSD:  state.LastSD,
		SD:      applySD,
		Step:    ctx.Step,
		TreeSD:  treeSD,
		Rules:   bundle.Rows,
	})
	merged := finalizeCycle(state, incoming, ctx, applySeq)
	commit := merged.Runs[len(merged.Runs)-1]
	model.AppendJournal(opts.Profile, model.JournalEvent{
		Profile: opts.Profile,
		RID:     ctx.Step,
		Ph:      "commit",
		Seq:     applySeq + 1,
		PrevSD:  state.LastSD,
		SD:      commit.SD,
		Step:    merged.Step,
		TreeSD:  treeSD,
		Rules:   merged.Rules,
	})
	model.SaveState(opts.Profile, merged)
	model.WriteSnapshot(opts.Profile, merged)
	return nil
}

func finalizeCycle(state, incoming model.PersistedState, ctx model.Context, applySeq int) model.PersistedState {
	merged := enforce.FoldState(state, incoming, ctx)
	layout := model.LoadLayout()
	commitSD := model.ScopeDigest(merged.Rules, layout)
	merged.Runs = append(merged.Runs, model.RunRow{
		RID: strconv.Itoa(ctx.Step),
		Ph:  "commit",
		SD:  commitSD,
	})
	merged.LastSeq = applySeq + 1
	merged.LastSD = commitSD
	return merged
}
