package journal

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"g7.example/attest/m7"
)

type replayState struct {
	active      map[string]Observation
	maxRevision uint64
	changed     []string
}

func parseEvent(raw []byte) (Event, error) {
	value, err := decodeObject(raw)
	if err != nil {
		return Event{}, err
	}
	canonical, err := canonicalObject(value)
	if err != nil {
		return Event{}, err
	}
	eventID, err := requiredString(value, "event_id")
	if err != nil {
		return Event{}, err
	}
	assayID, err := requiredString(value, "assay_id")
	if err != nil {
		return Event{}, err
	}
	seq, err := requiredUint(value, "seq")
	if err != nil {
		return Event{}, err
	}
	kind, err := requiredString(value, "kind")
	if err != nil {
		return Event{}, err
	}
	event := Event{
		EventID: eventID, AssayID: assayID, Seq: seq, Kind: kind,
		Digest: digestText(canonical), Canonical: canonical, Occurrences: 1,
	}
	switch kind {
	case "measurement", "supersede":
		event.Revision, err = requiredUint(value, "revision")
		if err != nil {
			return Event{}, err
		}
		event.MeasuredTm, err = requiredFinite(value, "measured_tm")
		if err != nil {
			return Event{}, err
		}
		event.UplinkTm, err = requiredFinite(value, "uplink_tm")
		if err != nil {
			return Event{}, err
		}
		event.InstrumentRun, err = requiredString(value, "instrument_run")
		if err != nil {
			return Event{}, err
		}
		if kind == "supersede" {
			event.TargetEventID, err = requiredString(value, "target_event_id")
		}
	case "tombstone":
		event.TargetEventID, err = requiredString(value, "target_event_id")
	case "rollback":
		event.ThroughSeq, err = requiredUint(value, "through_seq")
	default:
		return Event{}, fmt.Errorf("unsupported kind %q", kind)
	}
	if err != nil {
		return Event{}, err
	}
	return event, nil
}

func loadEvents(path string) ([]Event, int, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, 0, err
	}
	defer file.Close()

	events := make([]Event, 0)
	byID := make(map[string]int)
	duplicates := 0
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 4096), 4*1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		event, parseErr := parseEvent([]byte(line))
		if parseErr != nil {
			return nil, 0, parseErr
		}
		if index, exists := byID[event.EventID]; exists {
			if events[index].Canonical != event.Canonical {
				return nil, 0, fmt.Errorf("conflicting event id %s", event.EventID)
			}
			events[index].Occurrences++
			duplicates++
			continue
		}
		byID[event.EventID] = len(events)
		events = append(events, event)
	}
	if err := scanner.Err(); err != nil {
		return nil, 0, err
	}
	if len(events) == 0 {
		return nil, 0, fmt.Errorf("empty journal")
	}
	for _, event := range events {
		if event.TargetEventID == "" {
			continue
		}
		index, exists := byID[event.TargetEventID]
		if !exists {
			return nil, 0, fmt.Errorf("missing target %s", event.TargetEventID)
		}
		if events[index].AssayID != event.AssayID {
			return nil, 0, fmt.Errorf("cross-assay target %s", event.TargetEventID)
		}
	}
	return events, duplicates, nil
}

func loadPolicy(path string) (Policy, string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Policy{}, "", err
	}
	value, err := decodeObject(raw)
	if err != nil {
		return Policy{}, "", err
	}
	canonical, err := canonicalObject(value)
	if err != nil {
		return Policy{}, "", err
	}
	var policy Policy
	if err := json.Unmarshal([]byte(canonical), &policy); err != nil {
		return Policy{}, "", err
	}
	if policy.Schema != "qpcr-policy-v2" || policy.NonstressToleranceC <= 0 {
		return Policy{}, "", fmt.Errorf("invalid policy")
	}
	seen := make(map[string]bool)
	for _, assayID := range policy.StressAssays {
		if assayID == "" || seen[assayID] {
			return Policy{}, "", fmt.Errorf("invalid stress assay list")
		}
		seen[assayID] = true
	}
	return policy, digestText(canonical), nil
}

func observation(event Event) Observation {
	return Observation{
		EventID: event.EventID, AssayID: event.AssayID, Seq: event.Seq,
		Revision: event.Revision, MeasuredTm: event.MeasuredTm,
		UplinkTm: event.UplinkTm, InstrumentRun: event.InstrumentRun,
	}
}

func applyEvent(state *replayState, event Event) string {
	switch event.Kind {
	case "measurement":
		if event.Revision < state.maxRevision {
			return "stale"
		}
		state.maxRevision = event.Revision
		state.active[event.EventID] = observation(event)
		state.changed = append(state.changed, event.Digest)
		return "accepted"
	case "supersede":
		delete(state.active, event.TargetEventID)
		if event.Revision < state.maxRevision {
			return "stale"
		}
		state.maxRevision = event.Revision
		state.active[event.EventID] = observation(event)
		state.changed = append(state.changed, event.Digest)
		return "superseded"
	case "tombstone":
		if _, exists := state.active[event.TargetEventID]; !exists {
			return "noop"
		}
		delete(state.active, event.TargetEventID)
		state.changed = append(state.changed, event.Digest)
		return "tombstoned"
	case "rollback":
		changed := false
		for eventID, item := range state.active {
			if item.Seq == event.ThroughSeq {
				delete(state.active, eventID)
				changed = true
			}
		}
		if changed {
			state.changed = append(state.changed, event.Digest)
			return "rolled_back"
		}
		return "noop"
	}
	return "noop"
}

func activeObservation(state *replayState) (Observation, bool) {
	var selected Observation
	found := false
	for _, item := range state.active {
		if !found || item.Revision > selected.Revision ||
			(item.Revision == selected.Revision && item.Seq > selected.Seq) ||
			(item.Revision == selected.Revision && item.Seq == selected.Seq && item.EventID > selected.EventID) {
			selected = item
			found = true
		}
	}
	return selected, found
}

func SettlePackage(journalPath, configPath string) (Package, error) {
	events, duplicates, err := loadEvents(journalPath)
	if err != nil {
		return Package{}, err
	}
	policy, configDigest, err := loadPolicy(configPath)
	if err != nil {
		return Package{}, err
	}

	digests := make([]string, 0, len(events))
	states := make(map[string]*replayState)
	trace := make([]TraceRow, 0, len(events))
	for _, event := range events {
		digests = append(digests, event.Digest)
		state := states[event.AssayID]
		if state == nil {
			state = &replayState{active: make(map[string]Observation)}
			states[event.AssayID] = state
		}
		effect := applyEvent(state, event)
		trace = append(trace, TraceRow{
			EventID: event.EventID, AssayID: event.AssayID, Seq: event.Seq,
			Kind: event.Kind, EventDigest: event.Digest,
			Occurrences: event.Occurrences, Effect: effect,
		})
	}
	journalDigest := digestText(strings.Join(digests, "\n"))
	cacheKey := digestText("qpcr-journal-v2\n" + journalDigest + "\n" + configDigest)
	stressSet := make(map[string]bool)
	for _, assayID := range policy.StressAssays {
		stressSet[assayID] = true
	}

	assays := make([]AssayRow, 0, len(states))
	summary := Summary{TraceTotal: len(trace)}
	for assayID, state := range states {
		active, ok := activeObservation(state)
		if !ok {
			return Package{}, fmt.Errorf("assay %s has no active observation", assayID)
		}
		classification, tolerance, classErr := m7.Classify(
			active.MeasuredTm, active.UplinkTm, policy.NonstressToleranceC, stressSet[assayID],
		)
		if classErr != nil {
			return Package{}, classErr
		}
		witnessBody := "qpcr-witness-v2\n" + configDigest + "\n" + strings.Join(state.changed, "\n")
		row := AssayRow{
			AssayID: assayID, ActiveEventID: active.EventID, Revision: active.Revision,
			InstrumentRun: active.InstrumentRun, MeasuredTm: active.MeasuredTm,
			UplinkTm: active.UplinkTm, DeltaC: active.MeasuredTm - active.UplinkTm,
			ToleranceC: tolerance, Policy: "band", Classification: classification,
			Witness: digestText(witnessBody),
		}
		if stressSet[assayID] {
			row.Policy = "strict"
		}
		switch classification {
		case "within":
			summary.WithinTotal++
		case "over":
			summary.OverTotal++
		case "outside":
			summary.OutsideTotal++
		}
		assays = append(assays, row)
	}
	sort.Slice(assays, func(i, j int) bool { return assays[i].AssayID < assays[j].AssayID })
	summary.AssaysTotal = len(assays)
	return Package{
		Schema: "qpcr-attestation-v2",
		Provenance: Provenance{
			JournalDigest: journalDigest, ConfigDigest: configDigest, CacheKey: cacheKey,
			LogicalEvents: len(events), DuplicateEvents: duplicates,
		},
		Assays: assays, Trace: trace, Summary: summary,
	}, nil
}
