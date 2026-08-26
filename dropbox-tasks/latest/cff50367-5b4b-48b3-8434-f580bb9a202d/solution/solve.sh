#!/bin/bash
set -euo pipefail
cd /app/environment

cat > model/types.go <<'EOF'
package model

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

const (
	AppRoot   = "/app"
	EnvRoot   = AppRoot + "/environment"
	OutDir    = AppRoot + "/output"
	BinDir    = AppRoot + "/bin"
	CarryMark = 0.5
)

type Row struct {
	Seq          int     `json:"seq"`
	Key          string  `json:"key"`
	Value        string  `json:"value"`
	Op           string  `json:"op"`
	Epoch        int     `json:"epoch"`
	Generation   int     `json:"generation"`
	Mark         float64 `json:"mark"`
	Phase        string  `json:"phase"`
	RunID        string  `json:"run_id"`
	Scope        string  `json:"scope,omitempty"`
	Origin       string  `json:"origin,omitempty"`
	Profile      string  `json:"profile,omitempty"`
	EffectiveSeq int     `json:"effective_seq,omitempty"`
}

type Context struct {
	Profile string
	Epoch   int
	Phase   string
	RunID   string
}

type Entry struct {
	Key        string
	Value      string
	Epoch      int
	Generation int
	Mark       float64
	Scope      string
	Origin     string
}

type ViewState struct {
	Entries []Entry
	Phase   string
	RunID   string
}

type SealMeta struct {
	Epoch           int    `json:"epoch"`
	Counter         int    `json:"counter"`
	GenerationFloor int    `json:"generation_floor,omitempty"`
	SealRev         int    `json:"seal_rev"`
	Tag             string `json:"tag"`
}

type ProfileLayout struct {
	Epoch           int
	Counter         int
	GenerationFloor int
	SealRev         int
	Tag             string
	SeedEpoch       int
	SeedGeneration  int
	SeedMark        float64
	InheritsFrom    string
	SharedKeys      []string
}

type RunRow struct {
	RunID          string `json:"run_id"`
	Phase          string `json:"phase"`
	ScopeDigest    string `json:"scope_digest"`
	PreviousDigest string `json:"previous_digest"`
}

type EntryRow struct {
	Key            string `json:"key"`
	Value          string `json:"value"`
	Phase          string `json:"phase"`
	Epoch          int    `json:"epoch"`
	SourceScope    string `json:"source_scope"`
	Origin         string `json:"origin"`
	ObservedDigest string `json:"observed_digest"`
}

type CheckpointRow struct {
	RunID           string `json:"run_id"`
	Phase           string `json:"phase"`
	FirstSeq        int    `json:"first_seq"`
	LastSeq         int    `json:"last_seq"`
	RecordCount     int    `json:"record_count"`
	EpochFloor      int    `json:"epoch_floor"`
	EpochCeil       int    `json:"epoch_ceil"`
	GenerationFloor int    `json:"generation_floor"`
	GenerationCeil  int    `json:"generation_ceil"`
	ScopeDigest     string `json:"scope_digest"`
}

type Trace struct {
	Profile     string          `json:"profile"`
	Epoch       int             `json:"epoch"`
	Counter     int             `json:"counter"`
	Runs        []RunRow        `json:"runs"`
	Entries     []EntryRow      `json:"entries"`
	Checkpoints []CheckpointRow `json:"checkpoints"`
}

type ProfileSpec struct {
	Name       string
	FixtureDir string
	Runs       []string
}

func TreeDigest(entries []Entry) string {
	type row struct {
		Key         string `json:"key"`
		Value       string `json:"value"`
		SourceScope string `json:"source_scope"`
	}
	rows := []row{}
	for _, e := range entries {
		rows = append(rows, row{Key: e.Key, Value: e.Value, SourceScope: e.Scope})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Key < rows[j].Key })
	data, _ := json.Marshal(rows)
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func ObservedDigest(e Entry) string {
	type row struct {
		Key         string `json:"key"`
		Value       string `json:"value"`
		Epoch       int    `json:"epoch"`
		Generation  int    `json:"generation"`
		SourceScope string `json:"source_scope"`
		Origin      string `json:"origin"`
	}
	payload, _ := json.Marshal(row{
		Key:         e.Key,
		Value:       e.Value,
		Epoch:       e.Epoch,
		Generation:  e.Generation,
		SourceScope: e.Scope,
		Origin:      e.Origin,
	})
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func WriteJSON(path string, v any) {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		panic(err)
	}
	if err := os.WriteFile(path, append(data, '\n'), 0644); err != nil {
		panic(err)
	}
}
EOF

cat > feeder/source.go <<'EOF'
package feeder

// RankFor returns the source rank used when canonical rows tie on epoch.
func RankFor(name string) int {
	switch name {
	case PrimaryName:
		return 0
	case ReplayName:
		return 1
	case ShadowName:
		return 2
	case SpillName:
		return 3
	case RetractName:
		return 4
	default:
		return -1
	}
}

// ReadOrder returns the durable overlay filenames in read order.
func ReadOrder() []string {
	return []string{PrimaryName, ReplayName, ShadowName, SpillName, RetractName}
}
EOF

cat > vault/seed.go <<'EOF'
package vault

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"jwksbound.local/mux/model"
	"jwksbound.local/mux/realms"
	"jwksbound.local/mux/notary"
)

// SeedRows parses the shipped drop-in tree for a profile into overlay rows.
// Weaker scopes are applied before stronger ones so stronger scopes win, files
// are walked alphabetically within a scope, and each raw line keeps its row
// operator (set/append/remove/delete).
func SeedRows(profile string) []model.Row {
	spec := realms.Lookup(profile)
	layout := notary.ReadProfileLayout()[profile]
	runID := ""
	if len(spec.Runs) > 0 {
		runID = spec.Runs[0]
	}
	root := spec.FixtureDir
	scopeOrder := []string{"cache", "tenant", "issuer"}
	var rows []model.Row
	seq := 0
	for _, scope := range scopeOrder {
		dir := filepath.Join(root, scope)
		files, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		names := []string{}
		for _, f := range files {
			if f.IsDir() {
				continue
			}
			names = append(names, f.Name())
		}
		sort.Strings(names)
		for _, name := range names {
			data, err := os.ReadFile(filepath.Join(dir, name))
			if err != nil {
				continue
			}
			for _, raw := range strings.Split(string(data), "\n") {
				line := strings.TrimSpace(raw)
				if line == "" || strings.HasPrefix(line, "#") {
					continue
				}
				seq++
				rows = append(rows, parseLine(line, scope, name, seq, layout, runID))
			}
		}
	}
	return rows
}

func parseLine(line, scope, origin string, seq int, layout model.ProfileLayout, runID string) model.Row {
	row := model.Row{
		Seq:        seq,
		Epoch:      layout.SeedEpoch,
		Generation: layout.SeedGeneration,
		Mark:       layout.SeedMark,
		Phase:      "apply",
		RunID:      runID,
		Scope:      scope,
		Origin:     origin,
	}
	if strings.HasSuffix(line, "!") {
		row.Op = "delete"
		row.Key = strings.TrimSpace(strings.TrimSuffix(line, "!"))
		return row
	}
	if idx := strings.Index(line, "+="); idx >= 0 {
		row.Op = "append"
		row.Key = strings.TrimSpace(line[:idx])
		row.Value = strings.TrimSpace(line[idx+2:])
		return row
	}
	if idx := strings.Index(line, "-="); idx >= 0 {
		row.Op = "remove"
		row.Key = strings.TrimSpace(line[:idx])
		row.Value = strings.TrimSpace(line[idx+2:])
		return row
	}
	idx := strings.Index(line, "=")
	row.Op = "set"
	row.Key = strings.TrimSpace(line[:idx])
	row.Value = strings.TrimSpace(line[idx+1:])
	return row
}
EOF

cat > vault/reader.go <<'EOF'
package vault

import (
	"encoding/json"
	"os"
	"sort"
	"strconv"

	"jwksbound.local/mux/model"
	"jwksbound.local/mux/feeder"
)

const seedRank = -1

// LoadPrimary returns just the shipped drop-in tree for a profile.
func LoadPrimary(profile string) []model.Row {
	return SeedRows(profile)
}

// Compose merges the shipped drop-in tree with every durable overlay journal
// into a canonical row stream, resolving duplicate rows by epoch then source
// rank then read order.
func Compose(profile string) []model.Row {
	type ranked struct {
		score [3]int
		row   model.Row
	}
	chosen := map[string]ranked{}
	sourceIndex := 0

	consider := func(rec model.Row, rank int) {
		if rec.Profile != "" && rec.Profile != profile {
			sourceIndex++
			return
		}
		key := journalKey(rec)
		next := ranked{score: [3]int{rec.Epoch, rank, sourceIndex}, row: rec}
		if prev, ok := chosen[key]; !ok || next.score[0] > prev.score[0] ||
			(next.score[0] == prev.score[0] && next.score[1] > prev.score[1]) ||
			(next.score[0] == prev.score[0] && next.score[1] == prev.score[1] && next.score[2] >= prev.score[2]) {
			chosen[key] = next
		}
		sourceIndex++
	}

	for _, rec := range SeedRows(profile) {
		consider(rec, seedRank)
	}
	for _, name := range feeder.ReadOrder() {
		rank := feeder.RankFor(name)
		for _, rec := range loadOne(feeder.PathFor(profile, name)) {
			consider(rec, rank)
		}
	}

	var out []model.Row
	for _, item := range chosen {
		out = append(out, item.row)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Seq == out[j].Seq {
			if out[i].RunID == out[j].RunID {
				if out[i].Phase == out[j].Phase {
					if out[i].Key == out[j].Key {
						return out[i].Op < out[j].Op
					}
					return out[i].Key < out[j].Key
				}
				return out[i].Phase < out[j].Phase
			}
			return out[i].RunID < out[j].RunID
		}
		return out[i].Seq < out[j].Seq
	})
	return out
}

func loadOne(path string) []model.Row {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var rows []model.Row
	if err := json.Unmarshal(data, &rows); err != nil {
		return nil
	}
	return rows
}

func journalKey(rec model.Row) string {
	return rec.RunID + "\x00" + rec.Phase + "\x00" + rec.Key + "\x00" + rec.Op + "\x00" + strconv.Itoa(rec.Seq)
}
EOF

cat > vault/segment.go <<'EOF'
package vault

import (
	"sort"

	"jwksbound.local/mux/model"
)

// SelectSegment returns the canonical rows that belong to the active context.
func SelectSegment(rows []model.Row, ctx model.Context) []model.Row {
	var out []model.Row
	for _, rec := range rows {
		if rec.RunID != ctx.RunID || rec.Phase != ctx.Phase {
			continue
		}
		out = append(out, rec)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Seq == out[j].Seq {
			return out[i].Key < out[j].Key
		}
		return out[i].Seq < out[j].Seq
	})
	return out
}
EOF

cat > quorum/filter.go <<'EOF'
package quorum

import (
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/notary"
)

func Floor(profile string) int {
	layout := notary.ReadLayout()
	meta := layout[profile]
	return meta.GenerationFloor
}

// Active keeps canonical rows eligible for phase reconciliation.
func Active(rows []model.Row, floor int) []model.Row {
	var out []model.Row
	for _, rec := range rows {
		if rec.Generation >= floor {
			out = append(out, rec)
		}
	}
	return out
}
EOF

cat > lapse/defer.go <<'EOF'
package lapse

import "jwksbound.local/mux/model"

// ActivatePending removes keys whose deferred tombstone has come due before the
// row at the given sequence is applied.
func ActivatePending(entries map[string]model.Entry, seq int, pending map[string]int) {
	for key, eff := range pending {
		if eff < seq {
			delete(entries, key)
			delete(pending, key)
		}
	}
}

// QueueTombstone applies an immediate delete when effective_seq is zero, or
// records a deferred tombstone for later activation.
func QueueTombstone(rec model.Row, pending map[string]int, entries map[string]model.Entry) {
	if rec.Op != "delete" && rec.Op != "retract" {
		return
	}
	if rec.EffectiveSeq == 0 {
		delete(entries, rec.Key)
		return
	}
	pending[rec.Key] = rec.EffectiveSeq
}
EOF

cat > weave/settle.go <<'EOF'
package weave

import (
	"sort"
	"strings"

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
			lapse.QueueTombstone(rec, pending, entries)
			continue
		}
		prev, ok := entries[rec.Key]
		if rec.Op == "set" || !ok {
			entries[rec.Key] = mkEntry(rec, rec.Value)
			continue
		}
		parts := tokenSplit(prev.Value)
		switch rec.Op {
		case "append":
			parts = append(parts, rec.Value)
		case "remove":
			parts = tokenRemove(parts, rec.Value)
		default:
			entries[rec.Key] = mkEntry(rec, rec.Value)
			continue
		}
		entries[rec.Key] = mkEntry(rec, strings.Join(parts, ","))
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

func mkEntry(rec model.Row, value string) model.Entry {
	return model.Entry{
		Key:        rec.Key,
		Value:      value,
		Epoch:      rec.Epoch,
		Generation: rec.Generation,
		Mark:       rec.Mark,
		Scope:      rec.Scope,
		Origin:     rec.Origin,
	}
}

func tokenSplit(value string) []string {
	var out []string
	for _, p := range strings.Split(value, ",") {
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

func tokenRemove(parts []string, token string) []string {
	var out []string
	for _, p := range parts {
		if p != token {
			out = append(out, p)
		}
	}
	return out
}
EOF

cat > weave/carry.go <<'EOF'
package weave

import "jwksbound.local/mux/model"

// CarryFromSettle selects the settle-view entries that carry into the next run.
func CarryFromSettle(state model.ViewState) map[string]model.Entry {
	out := map[string]model.Entry{}
	for _, e := range state.Entries {
		if e.Mark >= model.CarryMark {
			out[e.Key] = e
		}
	}
	return out
}
EOF

cat > weave/inherit.go <<'EOF'
package weave

import (
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/realms"
	"jwksbound.local/mux/notary"
)

// InheritShared seeds shared keys from the parent profile's final settle view.
func InheritShared(profile string) map[string]model.Entry {
	layout := notary.ReadProfileLayout()
	meta, ok := layout[profile]
	if !ok || meta.InheritsFrom == "" || len(meta.SharedKeys) == 0 {
		return nil
	}
	parent := realms.Lookup(meta.InheritsFrom)
	if len(parent.Runs) == 0 {
		return nil
	}
	lastRun := parent.Runs[len(parent.Runs)-1]
	auth := notary.Authority(parent.Name)
	state := RunPhase(parent, lastRun, "settle", auth.Epoch)
	out := map[string]model.Entry{}
	for _, key := range meta.SharedKeys {
		for _, e := range state.Entries {
			if e.Key == key {
				out[key] = e
			}
		}
	}
	return out
}
EOF

cat > weave/runner.go <<'EOF'
package weave

import (
	"jwksbound.local/mux/vault"
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/quorum"
)

// RunPhase builds the reconciled view for one profile run and phase.
func RunPhase(profile model.ProfileSpec, runID, phaseName string, epochVal int) model.ViewState {
	ctx := model.Context{Profile: profile.Name, Epoch: epochVal, Phase: phaseName, RunID: runID}
	records := vault.Compose(profile.Name)
	floor := quorum.Floor(profile.Name)
	records = quorum.Active(records, floor)
	segments := vault.SelectSegment(records, ctx)
	state := model.ViewState{Phase: phaseName, RunID: runID}
	if phaseName == "settle" {
		applyState := RunPhase(profile, runID, "apply", epochVal)
		return ReconcilePhase(applyState, segments)
	}
	if idx := runIndex(profile.Runs, runID); idx == 0 {
		for _, e := range InheritShared(profile.Name) {
			state.Entries = append(state.Entries, e)
		}
	} else if idx > 0 {
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
EOF

cat > notary/merge.go <<'EOF'
package notary

import "jwksbound.local/mux/model"

// CombineSeal folds incoming seal metadata into a base record.
func CombineSeal(base, incoming model.SealMeta) model.SealMeta {
	out := base
	if incoming.Epoch > out.Epoch {
		out.Epoch = incoming.Epoch
	}
	if incoming.Counter > out.Counter {
		out.Counter = incoming.Counter
	}
	if incoming.SealRev > out.SealRev {
		out.SealRev = incoming.SealRev
	}
	if incoming.Tag != "" {
		out.Tag = incoming.Tag
	}
	return out
}
EOF

cat > extent/bounds.go <<'EOF'
package extent

import "jwksbound.local/mux/model"

// EnrichSpan fills the sequence, epoch, and generation bounds for a checkpoint.
func EnrichSpan(point model.CheckpointRow, rows []model.Row) model.CheckpointRow {
	for i, row := range rows {
		if i == 0 || row.Seq < point.FirstSeq {
			point.FirstSeq = row.Seq
		}
		if i == 0 || row.Seq > point.LastSeq {
			point.LastSeq = row.Seq
		}
		if i == 0 || row.Epoch < point.EpochFloor {
			point.EpochFloor = row.Epoch
		}
		if i == 0 || row.Epoch > point.EpochCeil {
			point.EpochCeil = row.Epoch
		}
		if i == 0 || row.Generation < point.GenerationFloor {
			point.GenerationFloor = row.Generation
		}
		if i == 0 || row.Generation > point.GenerationCeil {
			point.GenerationCeil = row.Generation
		}
	}
	return point
}
EOF

cat > dossier/builder.go <<'EOF'
package dossier

import (
	"path/filepath"
	"sort"

	"jwksbound.local/mux/vault"
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/quorum"
	"jwksbound.local/mux/weave"
	"jwksbound.local/mux/notary"
	"jwksbound.local/mux/extent"
)

// BuildReport assembles the effective trace from persisted state and layout.
func BuildReport(profile model.ProfileSpec) model.Trace {
	rows := vault.Compose(profile.Name)
	auth := notary.Authority(profile.Name)
	layout := notary.ReadProfileLayout()[profile.Name]
	for _, r := range rows {
		if r.Epoch > auth.Epoch {
			auth.Epoch = r.Epoch
		}
	}
	maxGeneration := 0
	for _, r := range rows {
		if r.Generation > maxGeneration {
			maxGeneration = r.Generation
		}
	}
	counter := auth.Counter
	if len(rows) > counter {
		counter = len(rows)
	}
	if maxGeneration > counter {
		counter = maxGeneration
	}
	if auth.SealRev > counter {
		counter = auth.SealRev
	}
	if layout.SealRev > counter {
		counter = layout.SealRev
	}
	floor := quorum.Floor(profile.Name)
	active := quorum.Active(rows, floor)

	var runs []model.RunRow
	var entries []model.EntryRow
	var checkpoints []model.CheckpointRow
	previous := ""
	for _, runID := range profile.Runs {
		applyState := weave.RunPhase(profile, runID, "apply", auth.Epoch)
		settleState := weave.RunPhase(profile, runID, "settle", auth.Epoch)
		applyDigest := model.TreeDigest(applyState.Entries)
		settleDigest := model.TreeDigest(settleState.Entries)
		runs = append(runs, model.RunRow{RunID: runID, Phase: "apply", ScopeDigest: applyDigest, PreviousDigest: previous})
		runs = append(runs, model.RunRow{RunID: runID, Phase: "settle", ScopeDigest: settleDigest, PreviousDigest: applyDigest})
		previous = settleDigest

		states := map[string]model.ViewState{"apply": applyState, "settle": settleState}
		digests := map[string]string{"apply": applyDigest, "settle": settleDigest}
		for _, phaseName := range []string{"apply", "settle"} {
			st := states[phaseName]
			seg := vault.SelectSegment(active, model.Context{Profile: profile.Name, Phase: phaseName, RunID: runID})
			checkpoints = append(checkpoints, extent.EnrichSpan(spanRow(runID, phaseName, digests[phaseName], seg), seg))
			for _, e := range st.Entries {
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
		if entries[i].Key != entries[j].Key {
			return entries[i].Key < entries[j].Key
		}
		if entries[i].Epoch != entries[j].Epoch {
			return entries[i].Epoch < entries[j].Epoch
		}
		if entries[i].Phase != entries[j].Phase {
			return entries[i].Phase < entries[j].Phase
		}
		if entries[i].Value != entries[j].Value {
			return entries[i].Value < entries[j].Value
		}
		if entries[i].SourceScope != entries[j].SourceScope {
			return entries[i].SourceScope < entries[j].SourceScope
		}
		if entries[i].Origin != entries[j].Origin {
			return entries[i].Origin < entries[j].Origin
		}
		return entries[i].ObservedDigest < entries[j].ObservedDigest
	})
	sort.Slice(checkpoints, func(i, j int) bool {
		if checkpoints[i].RunID == checkpoints[j].RunID {
			return checkpoints[i].Phase < checkpoints[j].Phase
		}
		return checkpoints[i].RunID < checkpoints[j].RunID
	})
	return model.Trace{
		Profile:     profile.Name,
		Epoch:       auth.Epoch,
		Counter:     counter,
		Runs:        runs,
		Entries:     entries,
		Checkpoints: checkpoints,
	}
}

func WriteReport(profile string, trace model.Trace) {
	path := filepath.Join(model.OutDir, "freshness-report.json")
	auth := notary.Authority(profile)
	layout := notary.ReadProfileLayout()[profile]
	sealRev := auth.SealRev
	if layout.SealRev > sealRev {
		sealRev = layout.SealRev
	}
	notary.SaveSeal(profile, model.SealMeta{
		Epoch:   trace.Epoch,
		Counter: trace.Counter,
		SealRev: sealRev,
		Tag:     auth.Tag,
	})
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
EOF

gofmt -w model/types.go feeder/source.go vault/seed.go vault/reader.go vault/segment.go quorum/filter.go lapse/defer.go weave/settle.go weave/carry.go weave/inherit.go weave/runner.go notary/merge.go extent/bounds.go dossier/builder.go
go build -o /app/bin/mux ./cmd/mux
for profile in amber beryl onyx; do
  rm -rf "/app/output/state/${profile}"
done
rm -f /app/output/freshness-report.json
for profile in amber beryl onyx; do
  /app/bin/mux audit --profile "$profile"
done
