package model

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const (
	AppRoot   = "/app"
	EnvRoot   = "/app/environment"
	StateRoot = "/app/state"
	OutFile   = "/app/output/rule_lineage.json"
	BinPath   = "/app/bin/arctl"
)

type Piece struct {
	Tier string `json:"tier"`
	Kind string `json:"kind"`
	Body string `json:"body"`
	Op   string `json:"op"`
	Src  string `json:"src"`
	Line int    `json:"line"`
}

type RuleRow struct {
	Kind string `json:"class"`
	Verb string `json:"action"`
	Slot string `json:"field"`
	Gen  int    `json:"generation"`
	Auth string `json:"observed_authority"`
}

type Bundle struct {
	Tag  string
	Rows []RuleRow
}

type RunRow struct {
	RID string `json:"reload_id"`
	Ph  string `json:"phase"`
	SD  string `json:"scope_digest"`
}

type NoteRow struct {
	Surface string `json:"surface"`
	Detail  string `json:"detail"`
}

type Report struct {
	Profile string    `json:"profile"`
	Runs    []RunRow  `json:"reloads"`
	Rules   []RuleRow `json:"rules"`
	Notes   []NoteRow `json:"notes"`
}

type Context struct {
	Profile string
	Step    int
	Ph      string
}

type TierLayout struct {
	Tiers map[string]struct {
		Rank int `json:"rank"`
	} `json:"tiers"`
	Joiner string `json:"digest_joiner"`
	Pair   string `json:"digest_pair"`
}

type ProfileSpec struct {
	Name           string `json:"name"`
	Fixture        string `json:"fixture"`
	Cycles         int    `json:"cycles"`
	AuthorityTier  string `json:"authority_tier"`
	InspectPasses  int    `json:"inspect_passes"`
	SeedGeneration int    `json:"seed_generation"`
}

type PersistedState struct {
	Profile string    `json:"profile"`
	Step    int       `json:"step"`
	LastSD  string    `json:"last_sd"`
	LastSeq int       `json:"last_seq"`
	Rules   []RuleRow `json:"rules"`
	Runs    []RunRow  `json:"runs"`
	Revoked []string  `json:"revoked"`
	Recov   []string  `json:"recov"`
	TreeSD  string    `json:"tree_sd"`
}

type JournalEvent struct {
	Profile string    `json:"profile"`
	RID     int       `json:"rid"`
	Ph      string    `json:"ph"`
	Seq     int       `json:"seq"`
	PrevSD  string    `json:"prev_sd"`
	SD      string    `json:"sd"`
	Step    int       `json:"step"`
	TreeSD  string    `json:"tree_sd"`
	Rules   []RuleRow `json:"rules"`
}

func LoadLayout() TierLayout {
	data, err := os.ReadFile(filepath.Join(EnvRoot, "runtime", "layout.json"))
	if err != nil {
		panic(err)
	}
	var layout TierLayout
	if err := json.Unmarshal(data, &layout); err != nil {
		panic(err)
	}
	if layout.Joiner == "" {
		layout.Joiner = ";"
	}
	if layout.Pair == "" {
		layout.Pair = ":"
	}
	return layout
}

func TierRank(layout TierLayout, tier string) int {
	if row, ok := layout.Tiers[tier]; ok {
		return row.Rank
	}
	return 99
}

func ScopeDigest(rows []RuleRow, layout TierLayout) string {
	parts := make([]string, 0, len(rows))
	for _, row := range rows {
		parts = append(parts, row.Kind+"="+row.Verb+":"+row.Slot+layout.Pair+row.Auth+layout.Pair+row.SrcName())
	}
	sort.Strings(parts)
	sum := sha256.Sum256([]byte(strings.Join(parts, layout.Joiner)))
	return hex.EncodeToString(sum[:])
}

func (r RuleRow) SrcName() string {
	return r.Auth
}

func TreeDigest(pieces []Piece, layout TierLayout) string {
	parts := make([]string, 0, len(pieces))
	for _, row := range pieces {
		parts = append(parts, row.Tier+layout.Pair+row.Src+layout.Pair+row.Kind+layout.Pair+row.Op+layout.Pair+row.Body)
	}
	sort.Strings(parts)
	sum := sha256.Sum256([]byte(strings.Join(parts, layout.Joiner)))
	return hex.EncodeToString(sum[:])
}

func StatePath(profile string) string {
	return filepath.Join(StateRoot, profile+".json")
}

func JournalPath(profile string) string {
	return filepath.Join(StateRoot, profile+".journal")
}

func SnapshotPath(profile string) string {
	return filepath.Join(EnvRoot, "store", "snapshots", profile+".json")
}

func EnsureDirs() {
	_ = os.MkdirAll(StateRoot, 0755)
	_ = os.MkdirAll(filepath.Dir(OutFile), 0755)
	_ = os.MkdirAll(filepath.Join(EnvRoot, "store", "snapshots"), 0755)
}

func SplitBody(raw string) (string, string) {
	parts := strings.SplitN(raw, ":", 2)
	if len(parts) != 2 {
		return raw, ""
	}
	return strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
}
