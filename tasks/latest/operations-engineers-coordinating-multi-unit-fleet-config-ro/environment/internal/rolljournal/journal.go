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
	_, _ = path, scenarioID
	return Entry{}, false, nil
}

func Append(path string, e Entry) error {
	_, _ = path, e
	return nil
}

func ensureParent(path string) error {
	return os.MkdirAll(filepath.Dir(path), 0o755)
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
