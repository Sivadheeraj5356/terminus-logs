package model

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
)

func LoadState(profile string) PersistedState {
	data, err := os.ReadFile(StatePath(profile))
	if err != nil {
		return PersistedState{Profile: profile}
	}
	var state PersistedState
	if err := json.Unmarshal(data, &state); err != nil {
		return PersistedState{Profile: profile, Recov: []string{"checkpoint-json"}}
	}
	if state.Profile == "" {
		state.Profile = profile
	}
	return state
}

func SaveState(profile string, state PersistedState) {
	data, err := json.Marshal(state)
	if err != nil {
		panic(err)
	}
	tmp := StatePath(profile) + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		panic(err)
	}
	if err := os.Rename(tmp, StatePath(profile)); err != nil {
		panic(err)
	}
}

func LoadJournal(profile string) ([]JournalEvent, []string) {
	f, err := os.Open(JournalPath(profile))
	if err != nil {
		return nil, nil
	}
	defer f.Close()
	var events []JournalEvent
	var recovered []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		var event JournalEvent
		if err := json.Unmarshal(scanner.Bytes(), &event); err != nil {
			recovered = append(recovered, "ignored-journal-line")
			continue
		}
		if event.Profile == profile && event.Seq > 0 {
			events = append(events, event)
		}
	}
	if scanner.Err() != nil {
		recovered = append(recovered, "journal-read")
	}
	return events, recovered
}

func AppendJournal(profile string, event JournalEvent) {
	if err := os.MkdirAll(filepath.Dir(JournalPath(profile)), 0755); err != nil {
		panic(err)
	}
	data, err := json.Marshal(event)
	if err != nil {
		panic(err)
	}
	f, err := os.OpenFile(JournalPath(profile), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	if _, err := f.Write(append(data, '\n')); err != nil {
		panic(err)
	}
}

func RebuildState(profile string) PersistedState {
	checkpoint := LoadState(profile)
	events, recovered := LoadJournal(profile)
	fromJournal := replay(profile, events, recovered)
	if checkpoint.Step == fromJournal.Step &&
		checkpoint.LastSeq == fromJournal.LastSeq &&
		checkpoint.LastSD == fromJournal.LastSD &&
		checkpoint.TreeSD == fromJournal.TreeSD &&
		len(checkpoint.Rules) == len(fromJournal.Rules) {
		checkpoint.Recov = append(checkpoint.Recov, recovered...)
		return checkpoint
	}
	if fromJournal.Step > 0 {
		fromJournal.Recov = append(fromJournal.Recov, "checkpoint-replayed")
		return fromJournal
	}
	checkpoint.Recov = append(checkpoint.Recov, recovered...)
	return checkpoint
}

func replay(profile string, events []JournalEvent, recovered []string) PersistedState {
	state := PersistedState{Profile: profile, Recov: append([]string{}, recovered...)}
	expectedSeq := 1
	lastSD := ""
	for _, event := range events {
		if event.Seq != expectedSeq {
			state.Recov = append(state.Recov, "journal-gap")
			break
		}
		if event.PrevSD != lastSD {
			state.Recov = append(state.Recov, "journal-chain")
			break
		}
		row := RunRow{RID: strconv.Itoa(event.RID), Ph: event.Ph, SD: event.SD}
		state.Runs = append(state.Runs, row)
		state.LastSeq = event.Seq
		state.TreeSD = event.TreeSD
		if event.Ph == "commit" {
			state.Step = event.Step
			state.LastSD = event.SD
			state.Rules = append([]RuleRow{}, event.Rules...)
			lastSD = event.SD
		}
		expectedSeq++
	}
	return state
}

func ReadSnapshot(profile string) (PersistedState, bool) {
	data, err := os.ReadFile(SnapshotPath(profile))
	if err != nil {
		return PersistedState{}, false
	}
	var state PersistedState
	if err := json.Unmarshal(data, &state); err != nil {
		return PersistedState{}, false
	}
	return state, true
}

func WriteSnapshot(profile string, state PersistedState) {
	data, err := json.Marshal(state)
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(SnapshotPath(profile), data, 0644); err != nil {
		panic(err)
	}
}
