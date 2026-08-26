package journal

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"strconv"
)

func digestText(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}

func decodeObject(raw []byte) (map[string]any, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var value map[string]any
	if err := dec.Decode(&value); err != nil {
		return nil, err
	}
	if value == nil {
		return nil, fmt.Errorf("expected one JSON object")
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		return nil, fmt.Errorf("trailing JSON value")
	}
	return value, nil
}

func canonicalObject(value map[string]any) (string, error) {
	body, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func requiredString(value map[string]any, key string) (string, error) {
	raw, ok := value[key]
	if !ok {
		return "", fmt.Errorf("missing %s", key)
	}
	text, ok := raw.(string)
	if !ok || text == "" {
		return "", fmt.Errorf("%s must be a nonempty string", key)
	}
	return text, nil
}

func requiredUint(value map[string]any, key string) (uint64, error) {
	raw, ok := value[key]
	if !ok {
		return 0, fmt.Errorf("missing %s", key)
	}
	number, ok := raw.(json.Number)
	if !ok {
		return 0, fmt.Errorf("%s must be an integer", key)
	}
	return strconv.ParseUint(number.String(), 10, 64)
}

func requiredFinite(value map[string]any, key string) (float64, error) {
	raw, ok := value[key]
	if !ok {
		return 0, fmt.Errorf("missing %s", key)
	}
	number, ok := raw.(json.Number)
	if !ok {
		return 0, fmt.Errorf("%s must be numeric", key)
	}
	parsed, err := strconv.ParseFloat(number.String(), 64)
	if err != nil || math.IsNaN(parsed) || math.IsInf(parsed, 0) {
		return 0, fmt.Errorf("%s must be finite", key)
	}
	return parsed, nil
}
