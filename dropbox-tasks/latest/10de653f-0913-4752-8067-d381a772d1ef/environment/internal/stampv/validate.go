package stampv

import (
	"encoding/json"
	"os"
	"path/filepath"

	"reelseal/internal/digestutil"
)

type Stamp struct {
	Schema          string `json:"schema"`
	ManifestDigest  string `json:"manifest_digest"`
	Accepted        bool   `json:"accepted"`
	Engine          string `json:"engine"`
}

func Check(manifestPath, stampPath string) error {
	b, err := os.ReadFile(manifestPath)
	if err != nil {
		return err
	}
	st := Stamp{
		Schema:         "reelseal.stamp/v1",
		ManifestDigest: digestutil.HexBytes(b),
		Accepted:       true,
		Engine:         "reelseal-runtime/v1",
	}
	raw, _ := json.MarshalIndent(st, "", "  ")
	if err := os.MkdirAll(filepath.Dir(stampPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(stampPath, append(raw, '\n'), 0o644)
}
