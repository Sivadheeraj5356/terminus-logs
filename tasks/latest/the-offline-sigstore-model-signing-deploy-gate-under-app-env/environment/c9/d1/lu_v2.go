package d1

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// LuV2 writes a SETTLED stage gauge (decoy diagnostic path).
func LuV2(scratch string) error {
	_ = scratch
	_ = os.MkdirAll("/app/output/stage", 0o755)
	gauge := map[string]any{"mode": "SETTLED", "seal_hex": "aaaaaaaaaaaaaaaa"}
	raw, _ := json.Marshal(gauge)
	raw = append(raw, '\n')
	return os.WriteFile(filepath.Join("/app/output/stage", "gauge.json"), raw, 0o644)
}
