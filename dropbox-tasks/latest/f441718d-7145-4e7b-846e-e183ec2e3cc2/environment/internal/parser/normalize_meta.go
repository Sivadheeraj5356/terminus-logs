package parser

import (
	"sort"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// NormalizeKey lowercases and trims a metadata key.
func NormalizeKey(k string) string {
	return strings.TrimSpace(strings.ToLower(k))
}

// SortedKeys returns ascending keys for a string map.
func SortedKeys(m map[string]string) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// MetadataFingerprint creates a stable fingerprint string for metadata.
func MetadataFingerprint(m map[string]string) string {
	keys := SortedKeys(m)
	parts := make([]string, 0, len(keys))
	for _, k := range keys {
		parts = append(parts, k+"="+util.CollapseWS(m[k]))
	}
	return strings.Join(parts, "&")
}
