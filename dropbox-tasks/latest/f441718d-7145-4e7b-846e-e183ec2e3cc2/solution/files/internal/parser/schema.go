package parser

import (
	"fmt"
	"strings"
)

// SchemaVersion is the supported workflow schema identifier.
const SchemaVersion = "ai-workflow.v1"

// RequiredNodeFields lists mandatory node JSON fields.
var RequiredNodeFields = []string{"id", "name", "type"}

// SupportedNodeTypes is the allow-list of node types.
var SupportedNodeTypes = map[string]struct{}{
	"source": {}, "transform": {}, "train": {}, "eval": {}, "sink": {}, "audit": {}, "task": {},
}

// CheckType reports whether node type is supported.
func CheckType(t string) error {
	t = strings.TrimSpace(t)
	if t == "" {
		return fmt.Errorf("empty type")
	}
	if _, ok := SupportedNodeTypes[t]; !ok {
		return fmt.Errorf("unsupported node type %q", t)
	}
	return nil
}

// MergeDependsOn unions depends_on lists deterministically.
func MergeDependsOn(lists ...[]string) []string {
	seen := map[string]struct{}{}
	var out []string
	for _, list := range lists {
		for _, id := range list {
			id = strings.TrimSpace(id)
			if id == "" {
				continue
			}
			if _, ok := seen[id]; ok {
				continue
			}
			seen[id] = struct{}{}
			out = append(out, id)
		}
	}
	// insertion order already stable from inputs; callers should sort if needed
	return out
}
