package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

func statePath(root string) string {
	return filepath.Join(root, "register", "repair_state.json")
}

func writeRepairState(root string, entries []RepairEntry) error {
	sort.Slice(entries, func(i, j int) bool { return entries[i].GameID < entries[j].GameID })
	data, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return writeFileAtomic(statePath(root), data)
}

func loadRepairState(root string) ([]RepairEntry, error) {
	data, err := os.ReadFile(statePath(root))
	if err != nil {
		return nil, err
	}
	var entries []RepairEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		return nil, err
	}
	return entries, nil
}
