package ledger

import (
	"encoding/json"
	"os"
	"strings"
)

type File struct {
	Entries map[string]int `json:"entries"`
}

func Load(path string) (map[string]int, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return map[string]int{}, nil
		}
		return nil, err
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return nil, err
	}
	if f.Entries == nil {
		return map[string]int{}, nil
	}
	out := map[string]int{}
	for k, v := range f.Entries {
		player := strings.SplitN(k, "|", 2)[0]
		if prev, ok := out[player]; !ok || v > prev {
			out[player] = v
		}
	}
	return out, nil
}

func Save(path string, entries map[string]int) error {
	collapsed := map[string]int{}
	for k, v := range entries {
		player := strings.SplitN(k, "|", 2)[0]
		if prev, ok := collapsed[player]; !ok || v > prev {
			collapsed[player] = v
		}
	}
	raw, err := json.MarshalIndent(File{Entries: collapsed}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}
