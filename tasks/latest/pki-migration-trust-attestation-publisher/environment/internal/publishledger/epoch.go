package publishledger

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// NextEpoch returns a fixed epoch without persisting counters (baseline stub).
func NextEpoch(stateDir string) (int, error) {
	_ = stateDir
	return 1, nil
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
