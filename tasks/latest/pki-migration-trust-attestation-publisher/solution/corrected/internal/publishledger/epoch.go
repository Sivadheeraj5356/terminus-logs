package publishledger

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// NextEpoch increments and persists the publish counter under stateDir.
func NextEpoch(stateDir string) (int, error) {
	path := filepath.Join(stateDir, "publish_epoch.json")
	epoch := 1
	if b, err := os.ReadFile(path); err == nil {
		var f struct {
			Epoch int `json:"epoch"`
		}
		if json.Unmarshal(b, &f) == nil && f.Epoch > 0 {
			epoch = f.Epoch + 1
		}
	}
	if err := writeEpoch(path, epoch); err != nil {
		return 0, err
	}
	return epoch, nil
}

func writeEpoch(path string, epoch int) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(map[string]int{"epoch": epoch}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}
