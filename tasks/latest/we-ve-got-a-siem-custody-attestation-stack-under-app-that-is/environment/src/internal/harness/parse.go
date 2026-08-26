package harness

import (
	"encoding/json"
	"os"

	"chronctl/pkg/api"
)

func LoadPack(path string) (*api.Pack, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var pack api.Pack
	if err := json.Unmarshal(raw, &pack); err != nil {
		return nil, err
	}
	return &pack, nil
}
