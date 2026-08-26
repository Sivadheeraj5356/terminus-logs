package m7

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const SchemaVersion = "fleet.unit.v1"

type ScenarioFixture struct {
	Scenario     string   `json:"scenario"`
	Trigger      string   `json:"trigger"`
	UnitsTouched []string `json:"units_touched"`
}

type Event struct {
	Action  string `json:"action"`
	Unit    string `json:"unit"`
	TsIndex int    `json:"ts_index"`
}

type ScenarioOut struct {
	Scenario      string   `json:"scenario"`
	Trigger       string   `json:"trigger"`
	UnitsTouched  []string `json:"units_touched"`
	OrderedEvents []Event  `json:"ordered_events"`
}

type Trace struct {
	SchemaVersion string        `json:"schema_version"`
	Scenarios     []ScenarioOut `json:"scenarios"`
	TraceDigest   string        `json:"trace_digest"`
}

func loadRequires(unitsDir string) map[string][]string {
	out := make(map[string][]string)
	ents, _ := os.ReadDir(unitsDir)
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		raw, _ := os.ReadFile(filepath.Join(unitsDir, e.Name()))
		for _, line := range strings.Split(string(raw), "\n") {
			if strings.HasPrefix(line, "Requires=") {
				out[e.Name()] = strings.Fields(strings.TrimPrefix(line, "Requires="))
			}
		}
	}
	return out
}

func closure(trigger string, requires map[string][]string) map[string]struct{} {
	seen := map[string]struct{}{trigger: {}}
	changed := true
	for changed {
		changed = false
		for unit, deps := range requires {
			for _, dep := range deps {
				if _, ok := seen[dep]; ok {
					if _, have := seen[unit]; !have {
						seen[unit] = struct{}{}
						changed = true
					}
				}
			}
		}
	}
	return seen
}

func dependentsFirst(stopSet map[string]struct{}, requires map[string][]string) []string {
	var units []string
	for u := range stopSet {
		units = append(units, u)
	}
	sort.Strings(units)
	return units
}

func canonicalJSON(v any) ([]byte, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var generic any
	if err := json.Unmarshal(raw, &generic); err != nil {
		return nil, err
	}
	return json.Marshal(generic)
}

func Simulate(unitsDir, scenariosDir string, seed int) (Trace, error) {
	_ = seed
	requires := loadRequires(unitsDir)
	fixtures, _ := filepath.Glob(filepath.Join(scenariosDir, "*.json"))
	sort.Strings(fixtures)
	var scenarios []ScenarioOut
	ts := 0
	for _, fx := range fixtures {
		raw, _ := os.ReadFile(fx)
		var fix ScenarioFixture
		_ = json.Unmarshal(raw, &fix)
		stopSet := closure(fix.Trigger, requires)
		delete(stopSet, fix.Trigger)
		stops := dependentsFirst(stopSet, requires)
		var events []Event
		for _, u := range stops {
			ts++
			events = append(events, Event{Action: "stop", Unit: u, TsIndex: ts})
		}
		ts++
		events = append(events, Event{Action: "stop", Unit: fix.Trigger, TsIndex: ts})
		ts++
		events = append(events, Event{Action: "start", Unit: fix.Trigger, TsIndex: ts})
		scenarios = append(scenarios, ScenarioOut{
			Scenario:      fix.Scenario,
			Trigger:       fix.Trigger,
			UnitsTouched:  fix.UnitsTouched,
			OrderedEvents: events,
		})
	}
	canon, err := canonicalJSON(scenarios)
	if err != nil {
		return Trace{}, err
	}
	sum := sha256.Sum256(canon)
	return Trace{SchemaVersion: SchemaVersion, Scenarios: scenarios, TraceDigest: hex.EncodeToString(sum[:])}, nil
}
