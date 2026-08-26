package util

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"
)

func sortKeys(value any) any {
	switch v := value.(type) {
	case map[string]any:
		keys := make([]string, 0, len(v))
		for k := range v {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := make(map[string]any, len(v))
		for _, k := range keys {
			out[k] = sortKeys(v[k])
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = sortKeys(item)
		}
		return out
	default:
		return v
	}
}

func Fingerprint(body any) string {
	raw, err := json.Marshal(body)
	if err != nil {
		return ""
	}
	var decoded any
	if err := json.Unmarshal(raw, &decoded); err != nil {
		return ""
	}
	canonical, err := json.Marshal(sortKeys(decoded))
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:])
}
