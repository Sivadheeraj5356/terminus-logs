package export

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
)

func Digest(m Manifest) string {
	payload := map[string]any{
		"active_charts":    m.ActiveCharts,
		"values":           m.Values,
		"precedence_trail": m.PrecedenceTrail,
	}
	data, _ := json.Marshal(canonicalize(payload))
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func canonicalize(v any) any {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sortStrings(keys)
		out := make(map[string]any, len(t))
		for _, k := range keys {
			out[k] = canonicalize(t[k])
		}
		return out
	case []any:
		out := make([]any, len(t))
		for i, item := range t {
			out[i] = canonicalize(item)
		}
		return out
	case []TrailEntry:
		out := make([]any, len(t))
		for i, item := range t {
			out[i] = map[string]any{
				"chart": item.Chart, "path": item.Path, "value": item.Value,
				"layer": item.Layer, "ordinal": item.Ordinal,
			}
		}
		return out
	default:
		return v
	}
}

func sortStrings(xs []string) {
	for i := 0; i < len(xs); i++ {
		for j := i + 1; j < len(xs); j++ {
			if xs[j] < xs[i] {
				xs[i], xs[j] = xs[j], xs[i]
			}
		}
	}
}
