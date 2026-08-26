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
