package runbook

import (
	"encoding/json"
	"os"
	"path/filepath"

	"ot7/internal/paths"
)

type Entry struct {
	PlanDigestHex  string `json:"plan_digest_hex"`
	StableRuns     int    `json:"stable_runs"`
	LastGeneration int    `json:"last_generation"`
}

type Ledger struct {
	Generation  int              `json:"generation"`
	PolicyEpoch int              `json:"policy_epoch"`
	Entries     map[string]Entry `json:"entries"`
}

func Load() Ledger {
	p := filepath.Join(paths.Var, "run_ledger.json")
	b, err := os.ReadFile(p)
	if err != nil {
		return Ledger{Entries: map[string]Entry{}}
	}
	var ld Ledger
	if json.Unmarshal(b, &ld) != nil || ld.Entries == nil {
		return Ledger{Entries: map[string]Entry{}}
	}
	return ld
}

func (ld Ledger) Save() error {
	_ = os.MkdirAll(paths.Var, 0o777)
	b, _ := json.MarshalIndent(ld, "", "  ")
	return os.WriteFile(filepath.Join(paths.Var, "run_ledger.json"), b, 0o644)
}

func BumpStable(ld *Ledger, label, digest string, gen int) {
	if ld.Entries == nil {
		ld.Entries = map[string]Entry{}
	}
	prev, ok := ld.Entries[label]
	if !ok {
		ld.Entries[label] = Entry{PlanDigestHex: digest, StableRuns: 1, LastGeneration: gen}
		return
	}
	if prev.PlanDigestHex == digest {
		prev.StableRuns++
	} else {
		prev.StableRuns = 1
		prev.PlanDigestHex = digest
	}
	prev.LastGeneration = gen
	ld.Entries[label] = prev
}
