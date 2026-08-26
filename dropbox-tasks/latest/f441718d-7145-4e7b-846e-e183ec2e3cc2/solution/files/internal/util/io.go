package util

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// ReadJSON loads a JSON file into dest.
func ReadJSON(path string, dest any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, dest)
}

// WriteJSON writes v as indented JSON for human-readable state artifacts.
func WriteJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

// WriteCanonicalJSON writes compact sorted-key JSON (for digests and certificates).
func WriteCanonicalJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := CanonicalJSON(v)
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

// Exists reports whether path exists.
func Exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
