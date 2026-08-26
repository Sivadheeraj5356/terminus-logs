package seal

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func readBytes(path string) ([]byte, error) {
	return os.ReadFile(path)
}

func writeFile(path, body string) error {
	if err := os.MkdirAll(filepathDir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(body), 0o644)
}

func filepathDir(path string) string {
	i := strings.LastIndex(path, "/")
	if i < 0 {
		return "."
	}
	return path[:i]
}

func loadFloatMap(path string) (map[string]float64, error) {
	raw, err := readBytes(path)
	if err != nil {
		return nil, err
	}
	var generic map[string]any
	if err := json.Unmarshal(raw, &generic); err != nil {
		return nil, err
	}
	out := make(map[string]float64, len(generic))
	for k, v := range generic {
		switch t := v.(type) {
		case float64:
			out[k] = t
		case json.Number:
			f, err := t.Float64()
			if err != nil {
				return nil, err
			}
			out[k] = f
		default:
			return nil, fmt.Errorf("non-number in %s key %s", path, k)
		}
	}
	return out, nil
}

func mustNum(m map[string]any, key string) (float64, error) {
	v, ok := m[key]
	if !ok {
		return 0, fmt.Errorf("missing %s", key)
	}
	switch t := v.(type) {
	case float64:
		return t, nil
	case json.Number:
		return t.Float64()
	case string:
		return strconv.ParseFloat(t, 64)
	default:
		return 0, fmt.Errorf("bad number for %s", key)
	}
}

func mustStr(m map[string]any, key string) (string, error) {
	v, ok := m[key]
	if !ok {
		return "", fmt.Errorf("missing %s", key)
	}
	s, ok := v.(string)
	if !ok {
		return "", fmt.Errorf("bad string for %s", key)
	}
	return s, nil
}

func mustBool(m map[string]any, key string, def bool) bool {
	v, ok := m[key]
	if !ok {
		return def
	}
	b, ok := v.(bool)
	if !ok {
		return def
	}
	return b
}
