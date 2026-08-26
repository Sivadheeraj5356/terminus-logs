package decoys_f2

import (
	"encoding/json"
	"os"
)

func LaneScope(catalogPath string) ([]string, error) {
	raw, err := os.ReadFile(catalogPath)
	if err != nil {
		return nil, err
	}
	var doc struct {
		Objects map[string]any `json:"objects"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	keys := make([]string, 0, len(doc.Objects))
	for k := range doc.Objects {
		keys = append(keys, k)
	}
	return keys, nil
}
