package util

import (
	"encoding/json"
	"os"
)

type LogLine struct {
	Tick    uint64 `json:"tick"`
	Kind    string `json:"kind"`
	Detail  string `json:"detail,omitempty"`
	Epoch   uint64 `json:"epoch,omitempty"`
	Surface string `json:"surface,omitempty"`
}

func AppendJSONL(path string, line LogLine) error {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	b, err := json.Marshal(line)
	if err != nil {
		return err
	}
	if _, err := f.Write(append(b, '\n')); err != nil {
		return err
	}
	return nil
}
