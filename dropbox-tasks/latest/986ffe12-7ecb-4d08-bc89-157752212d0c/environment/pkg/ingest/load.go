package ingest

import (
	"encoding/json"
	"os"
)

func Load(path string) (*Bundle, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var bundle Bundle
	if err := json.Unmarshal(raw, &bundle); err != nil {
		return nil, err
	}
	return &bundle, nil
}
