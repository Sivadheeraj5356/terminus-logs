package ingest

import (
	"encoding/json"
	"fmt"
	"os"
)

func LoadManifest(path string) (Manifest, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Manifest{}, err
	}
	var m Manifest
	if err := json.Unmarshal(raw, &m); err != nil {
		return Manifest{}, err
	}
	if m.CheckpointDir == "" {
		return Manifest{}, fmt.Errorf("invalid manifest")
	}
	if m.Journal == "" && len(m.Lanes) == 0 {
		return Manifest{}, fmt.Errorf("invalid manifest")
	}
	return m, nil
}
