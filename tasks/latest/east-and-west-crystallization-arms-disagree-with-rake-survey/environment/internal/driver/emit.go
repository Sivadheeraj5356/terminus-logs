package driver

import (
	"encoding/json"
	"os"
)

// EmitReport writes the front report JSON.
func EmitReport(path string, rep Report) error {
	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}
