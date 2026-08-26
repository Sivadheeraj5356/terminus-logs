package io

import (
	"encoding/json"
	"os"
)

type Writer struct{}

func (Writer) Emit(path string, v any) error {
	raw, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}
