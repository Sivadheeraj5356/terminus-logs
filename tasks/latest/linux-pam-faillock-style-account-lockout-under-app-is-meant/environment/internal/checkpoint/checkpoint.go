package checkpoint

import (
	"encoding/json"
	"os"

	"baylock/internal/config"
)

type State struct {
	MigratedLegacy   bool   `json:"migrated_legacy"`
	JournalSeq       int    `json:"journal_seq"`
	ProjectionDigest string `json:"projection_digest"`
	RebuildAt        string `json:"rebuild_at"`
}

func Load() (*State, error) {
	data, err := os.ReadFile(config.CheckpointFile)
	if err != nil {
		if os.IsNotExist(err) {
			return &State{}, nil
		}
		return nil, err
	}
	var cp State
	if err := json.Unmarshal(data, &cp); err != nil {
		return nil, err
	}
	return &cp, nil
}

func Save(cp *State) error {
	if err := os.MkdirAll(config.StateDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cp, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(config.CheckpointFile, data, 0o644)
}
