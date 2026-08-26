package mediain

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"reelseal/internal/digestutil"
)

type Receipt struct {
	Schema      string `json:"schema"`
	Engine      string `json:"engine"`
	SourcePath  string `json:"source_path"`
	MediaDigest string `json:"media_digest"`
	Bytes       int    `json:"bytes"`
}

func Run(src, outPath string) error {
	if src == "" {
		src = "/app/fixtures/media-cache/bbb-sample.mp4"
	}
	if err := RefuseLegacy(src); err != nil {
		return err
	}
	b, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	rec := Receipt{
		Schema:      "reelseal.fetch/v1",
		Engine:      "reelseal-runtime/v1",
		SourcePath:  src,
		MediaDigest: digestutil.HexBytes(b),
		Bytes:       len(b),
	}
	raw, err := json.MarshalIndent(rec, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, '\n'), 0o644)
}

func RefuseLegacy(src string) error {
	clean := filepath.Clean(src)
	if strings.HasPrefix(clean, "/app/legacy") || strings.Contains(clean, "/legacy/") {
		return fmt.Errorf("legacy path refused: %s", src)
	}
	return nil
}
