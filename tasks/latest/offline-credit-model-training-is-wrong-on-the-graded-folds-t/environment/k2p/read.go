package k2p

import (
	"encoding/json"
	"os"
	"path/filepath"

	"pitctl/types"
)

func Read(foldID string) (types.JournalEntry, error) {
	var entry types.JournalEntry
	b, err := os.ReadFile(filepath.Join(Dir, foldID+".json"))
	if err != nil {
		return entry, err
	}
	err = json.Unmarshal(b, &entry)
	return entry, err
}
