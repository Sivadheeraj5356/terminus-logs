#!/bin/bash
set -euo pipefail

cd /app/environment

cat > compile/fold.go <<'EOF'
package compile

import (
	"bufio"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"arctl.local/arctl/model"
)

func LoadPieces(root string) []model.Piece {
	base := filepath.Join(model.EnvRoot, "fixtures", root)
	var out []model.Piece
	tiers, err := os.ReadDir(base)
	if err != nil {
		return out
	}
	for _, tierDir := range tiers {
		if !tierDir.IsDir() {
			continue
		}
		tier := tierDir.Name()
		files, err := os.ReadDir(filepath.Join(base, tier))
		if err != nil {
			continue
		}
		for _, file := range files {
			if file.IsDir() {
				continue
			}
			path := filepath.Join(base, tier, file.Name())
			rows, err := parseFile(path, tier, file.Name())
			if err != nil {
				continue
			}
			out = append(out, rows...)
		}
	}
	return out
}

func parseFile(path, tier, name string) ([]model.Piece, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []model.Piece
	scanner := bufio.NewScanner(f)
	idx := 0
	for scanner.Scan() {
		idx++
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		out = append(out, model.Piece{Tier: tier, Src: name, Line: idx, Op: "set"})
		switch {
		case strings.HasSuffix(line, "!"):
			out[len(out)-1].Kind = strings.TrimSpace(strings.TrimSuffix(line, "!"))
			out[len(out)-1].Op = "delete"
		case strings.Contains(line, "+="):
			parts := strings.SplitN(line, "+=", 2)
			out[len(out)-1].Kind = strings.TrimSpace(parts[0])
			out[len(out)-1].Body = strings.TrimSpace(parts[1])
			out[len(out)-1].Op = "append"
		case strings.Contains(line, "-="):
			parts := strings.SplitN(line, "-=", 2)
			out[len(out)-1].Kind = strings.TrimSpace(parts[0])
			out[len(out)-1].Body = strings.TrimSpace(parts[1])
			out[len(out)-1].Op = "remove"
		default:
			parts := strings.SplitN(line, "=", 2)
			if len(parts) != 2 {
				out = out[:len(out)-1]
				continue
			}
			out[len(out)-1].Kind = strings.TrimSpace(parts[0])
			out[len(out)-1].Body = strings.TrimSpace(parts[1])
		}
	}
	return out, scanner.Err()
}

func merge_inputs(items []model.Piece, ctx model.Context) []model.Bundle {
	layout := model.LoadLayout()
	ordered := append([]model.Piece{}, items...)
	sort.SliceStable(ordered, func(i, j int) bool {
		left := model.TierRank(layout, ordered[i].Tier)
		right := model.TierRank(layout, ordered[j].Tier)
		if left != right {
			return left > right
		}
		if ordered[i].Tier != ordered[j].Tier {
			return ordered[i].Tier > ordered[j].Tier
		}
		if ordered[i].Src != ordered[j].Src {
			return ordered[i].Src < ordered[j].Src
		}
		return ordered[i].Line < ordered[j].Line
	})
	byKind := map[string]model.RuleRow{}
	gen := ctx.Step
	if gen < 1 {
		gen = 1
	}
	for _, row := range ordered {
		current, ok := byKind[row.Kind]
		switch row.Op {
		case "delete":
			delete(byKind, row.Kind)
		case "append":
			if !ok {
				verb, slot := model.SplitBody(row.Body)
				byKind[row.Kind] = model.RuleRow{Kind: row.Kind, Verb: verb, Slot: slot, Gen: gen, Auth: row.Tier}
				continue
			}
			parts := []string{}
			if current.Slot != "" {
				parts = append(parts, strings.Split(current.Slot, ",")...)
			}
			parts = append(parts, row.Body)
			current.Slot = strings.Join(parts, ",")
			current.Auth = row.Tier
			byKind[row.Kind] = current
		case "remove":
			if !ok {
				continue
			}
			parts := []string{}
			for _, part := range strings.Split(current.Slot, ",") {
				if part != "" && part != row.Body {
					parts = append(parts, part)
				}
			}
			current.Slot = strings.Join(parts, ",")
			current.Auth = row.Tier
			byKind[row.Kind] = current
		default:
			verb, slot := model.SplitBody(row.Body)
			byKind[row.Kind] = model.RuleRow{Kind: row.Kind, Verb: verb, Slot: slot, Gen: gen, Auth: row.Tier}
		}
	}
	var rows []model.RuleRow
	for _, key := range sortedKeys(byKind) {
		rows = append(rows, byKind[key])
	}
	return []model.Bundle{{Tag: "primary", Rows: rows}}
}

func sortedKeys(byKind map[string]model.RuleRow) []string {
	var keys []string
	for key := range byKind {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func MergeInputs(items []model.Piece, ctx model.Context) []model.Bundle {
	return merge_inputs(items, ctx)
}
EOF

cat > load/apply.go <<'EOF'
package load

import (
	"sort"

	"arctl.local/arctl/model"
)

func pick_bundle(rows []model.Bundle, ctx model.Context) model.Bundle {
	layout := model.LoadLayout()
	byKind := map[string]model.RuleRow{}
	for _, bundle := range rows {
		for _, row := range bundle.Rows {
			current, ok := byKind[row.Kind]
			if !ok || model.TierRank(layout, row.Auth) < model.TierRank(layout, current.Auth) {
				byKind[row.Kind] = row
				continue
			}
			if model.TierRank(layout, row.Auth) == model.TierRank(layout, current.Auth) && row.Gen >= current.Gen {
				byKind[row.Kind] = row
			}
		}
	}
	var keys []string
	for key := range byKind {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	var out []model.RuleRow
	for _, key := range keys {
		out = append(out, byKind[key])
	}
	return model.Bundle{Tag: "active", Rows: out}
}

func PickBundle(rows []model.Bundle, ctx model.Context) model.Bundle {
	return pick_bundle(rows, ctx)
}
EOF

cat > enforce/stamp.go <<'EOF'
package enforce

import (
	"sort"

	"arctl.local/arctl/model"
)

func fold_state(base model.PersistedState, incoming model.PersistedState, ctx model.Context) model.PersistedState {
	if len(base.Rules) == 0 {
		return incoming
	}
	merged := incoming
	merged.Recov = append(append([]string{}, base.Recov...), incoming.Recov...)
	revoked := map[string]struct{}{}
	for _, key := range append(base.Revoked, incoming.Revoked...) {
		revoked[key] = struct{}{}
	}
	byKey := map[string]model.RuleRow{}
	for _, row := range base.Rules {
		if _, skip := revoked[row.Kind]; skip {
			continue
		}
		byKey[row.Kind] = row
	}
	for _, row := range incoming.Rules {
		if _, skip := revoked[row.Kind]; skip {
			continue
		}
		current, ok := byKey[row.Kind]
		if !ok || row.Gen > current.Gen || (row.Gen == current.Gen && row.Auth >= current.Auth) {
			byKey[row.Kind] = row
		}
	}
	merged.Rules = flattenRows(byKey)
	merged.Runs = append(append([]model.RunRow{}, base.Runs...), incoming.Runs...)
	merged.Step = incoming.Step
	merged.TreeSD = incoming.TreeSD
	merged.Revoked = append([]string{}, incoming.Revoked...)
	return merged
}

func flattenRows(byKey map[string]model.RuleRow) []model.RuleRow {
	var keys []string
	for key := range byKey {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	var out []model.RuleRow
	for _, key := range keys {
		out = append(out, byKey[key])
	}
	return out
}

func FoldState(base, incoming model.PersistedState, ctx model.Context) model.PersistedState {
	return fold_state(base, incoming, ctx)
}
EOF

cat > app/driver.go <<'EOF'
package app

import (
	"path/filepath"
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
		notes := []model.NoteRow{
			{Surface: "input_tree", Detail: filepath.Join(model.EnvRoot, "fixtures", spec.Fixture)},
			{Surface: "durable_state", Detail: model.StatePath(opts.Profile)},
			{Surface: "emission", Detail: model.OutFile},
		}
		report := emit.BuildReport(opts.Profile, state, spec, notes)
		emit.WriteReport(report)
		return nil
	}
	pieces := compile.LoadPieces(spec.Fixture)
	layout := model.LoadLayout()
	treeSD := model.TreeDigest(pieces, layout)
	ctx := model.Context{Profile: opts.Profile, Step: state.Step + 1, Ph: "apply"}
	bundles := compile.MergeInputs(pieces, ctx)
	bundle := load.PickBundle(bundles, ctx)
	incoming := model.PersistedState{
		Profile: opts.Profile,
		Step:    ctx.Step,
		TreeSD:  treeSD,
		Rules:   bundle.Rows,
		Revoked: revokedFromPieces(pieces),
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

func revokedFromPieces(pieces []model.Piece) []string {
	out := []string{}
	for _, row := range pieces {
		if row.Op == "delete" {
			out = append(out, row.Kind)
		}
	}
	return out
}
EOF

gofmt -w compile/fold.go load/apply.go enforce/stamp.go app/driver.go
go build -o /app/bin/arctl /app/environment/cmd/arctl

for profile in relay depot yard; do
  /app/bin/arctl reload --profile "$profile"
  /app/bin/arctl reload --profile "$profile"
done

/app/bin/arctl inspect --profile relay
