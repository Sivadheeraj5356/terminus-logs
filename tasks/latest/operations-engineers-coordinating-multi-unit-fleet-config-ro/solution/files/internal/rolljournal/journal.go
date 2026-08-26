package rolljournal

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
)

const DefaultPath = "/app/state/odip/rollout_journal.jsonl"

type Entry struct {
	ScenarioID       string `json:"scenario_id"`
	RolloutEpoch     int    `json:"rollout_epoch"`
	PlanDigest       string `json:"plan_digest"`
	LatticeDigest    string `json:"lattice_digest"`
	EpochSeal        string `json:"epoch_seal"`
	TopologyRevision string `json:"topology_revision"`
	WindowDigest     string `json:"window_digest"`
	BookingDigest    string `json:"booking_digest"`
}

func LatestForScenario(path, scenarioID string) (Entry, bool, error) {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return Entry{}, false, nil
		}
		return Entry{}, false, err
	}
	defer f.Close()
	var last Entry
	found := false
	s := bufio.NewScanner(f)
	for s.Scan() {
		line := s.Bytes()
		if len(line) == 0 {
			continue
		}
		var e Entry
		if err := json.Unmarshal(line, &e); err != nil {
			return Entry{}, false, err
		}
		if e.ScenarioID == scenarioID {
			last = e
			found = true
		}
	}
	if err := s.Err(); err != nil {
		return Entry{}, false, err
	}
	return last, found, nil
}

func Append(path string, e Entry) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	b, err := json.Marshal(e)
	if err != nil {
		return err
	}
	b = append(b, '\n')
	_, err = f.Write(b)
	return err
}

func ReadAll(path string) ([]Entry, error) {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []Entry
	s := bufio.NewScanner(f)
	for s.Scan() {
		line := s.Bytes()
		if len(line) == 0 {
			continue
		}
		var e Entry
		if err := json.Unmarshal(line, &e); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, s.Err()
}
