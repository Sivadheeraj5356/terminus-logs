package state

import (
	"encoding/json"
	"os"
)

func WriteSnapshot(path string, j *Journal) error {
	payload := struct {
		View []JournalEntry `json:"view"`
		Head uint64         `json:"head"`
	}{
		View: j.ExportSnapshot(),
		Head: j.HeadGeneration(),
	}
	b, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}
