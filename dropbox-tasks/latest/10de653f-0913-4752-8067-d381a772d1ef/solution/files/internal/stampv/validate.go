package stampv

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"reelseal/internal/digestutil"
)

type Stamp struct {
	Schema         string `json:"schema"`
	ManifestDigest string `json:"manifest_digest"`
	Accepted       bool   `json:"accepted"`
	Engine         string `json:"engine"`
}

func Check(manifestPath, stampPath string) error {
	b, err := os.ReadFile(manifestPath)
	if err != nil {
		return err
	}
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		return err
	}
	accepted := true
	reasons := []string{}
	for _, forbidden := range []string{"key_uri", "key_url", "key_http", "legacy_uri"} {
		if _, ok := m[forbidden]; ok {
			accepted = false
			reasons = append(reasons, forbidden)
		}
	}
	body := string(b)
	if strings.Contains(body, "http:\x2f\x2f") || strings.Contains(body, "https:\x2f\x2f") {
		accepted = false
		reasons = append(reasons, "http_leak")
	}
	if str(m["method"]) != "AES-128" {
		accepted = false
		reasons = append(reasons, "method")
	}
	if str(m["schema"]) != "reelseal.encryption-manifest/v1" {
		accepted = false
		reasons = append(reasons, "schema")
	}
	st := Stamp{
		Schema:         "reelseal.stamp/v1",
		ManifestDigest: digestutil.HexBytes(b),
		Accepted:       accepted,
		Engine:         "reelseal-runtime/v1",
	}
	raw, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(stampPath), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(stampPath, append(raw, '\n'), 0o644); err != nil {
		return err
	}
	if !accepted {
		return fmt.Errorf("hook rejected: %s", strings.Join(reasons, ","))
	}
	return nil
}

func str(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}
