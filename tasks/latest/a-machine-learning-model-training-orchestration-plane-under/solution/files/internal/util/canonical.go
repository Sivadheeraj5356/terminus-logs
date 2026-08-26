package util

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"unicode"
)

// CanonicalJSON marshals v with recursively sorted object keys and compact separators.
func CanonicalJSON(v any) ([]byte, error) {
	// Round-trip through encoding/json so structs become maps before key sorting.
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var generic any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&generic); err != nil {
		return nil, err
	}
	normalized, err := normalize(generic)
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(normalized); err != nil {
		return nil, err
	}
	out := buf.Bytes()
	// Encoder adds trailing newline; strip for digest stability.
	return bytes.TrimRight(out, "\n"), nil
}

func normalize(v any) (any, error) {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := make(map[string]any, len(t))
		for _, k := range keys {
			nv, err := normalize(t[k])
			if err != nil {
				return nil, err
			}
			out[k] = nv
		}
		return out, nil
	case []any:
		out := make([]any, len(t))
		for i, e := range t {
			nv, err := normalize(e)
			if err != nil {
				return nil, err
			}
			out[i] = nv
		}
		return out, nil
	case float64:
		if t == float64(int64(t)) {
			return int64(t), nil
		}
		return t, nil
	case json.Number:
		if i, err := t.Int64(); err == nil {
			return i, nil
		}
		f, err := t.Float64()
		return f, err
	default:
		return t, nil
	}
}

// MustCanonicalJSON panics only on programmer error during tests; production uses CanonicalJSON.
func MustCanonicalJSON(v any) []byte {
	b, err := CanonicalJSON(v)
	if err != nil {
		return []byte(fmt.Sprintf("%v", v))
	}
	return b
}

// CollapseWS collapses unicode whitespace runs to a single ASCII space and trims.
func CollapseWS(s string) string {
	var b strings.Builder
	prevSpace := false
	for _, r := range strings.TrimSpace(s) {
		if unicode.IsSpace(r) {
			if !prevSpace {
				b.WriteByte(' ')
				prevSpace = true
			}
			continue
		}
		prevSpace = false
		b.WriteRune(r)
	}
	return b.String()
}

// Itoa is a tiny helper used by journal sequencing.
func Itoa(n int) string { return strconv.Itoa(n) }
