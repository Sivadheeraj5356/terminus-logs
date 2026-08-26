package snapshot

import (
	"encoding/json"
	"os"

	"modgate/internal/models"
)

type fileShape struct {
	Entries map[string]models.SnapshotEntry `json:"entries"`
}

func Load(path string) (map[string]models.SnapshotEntry, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var f fileShape
	if err := json.Unmarshal(b, &f); err != nil {
		return nil, err
	}
	return f.Entries, nil
}
