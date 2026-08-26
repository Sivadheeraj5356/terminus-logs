package emit

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"

	"backuptrust/schema"
)

// WriteReport encodes the report with normative key order and a trailing newline.
func WriteReport(path string, report schema.Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(report); err != nil {
		return err
	}
	return os.WriteFile(path, buf.Bytes(), 0o644)
}
