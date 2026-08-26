package manifest

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const allowedVersion = 2

var allowedKeys = map[string]bool{
	"manifest_version": true,
	"orchard_id":       true,
	"profile":          true,
	"sensor_registry":  true,
	"readings":         true,
	"corrections":      true,
	"state_policy":     true,
}

type Manifest struct {
	Path           string
	Raw            []byte
	Dir            string
	OrchardID      string
	Profile        string
	SensorRegistry string
	Readings       []string
	Corrections    []string
	StatePolicy    string
}

func Load(path string) (Manifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Manifest{}, err
	}
	dir := filepath.Dir(path)
	m := Manifest{Path: path, Raw: data, Dir: dir}

	seen := map[string]int{}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "readings") {
			if err := parseArrayLine(line, "readings", &m.Readings, seen); err != nil {
				return Manifest{}, err
			}
			continue
		}
		if strings.HasPrefix(line, "corrections") {
			if err := parseArrayLine(line, "corrections", &m.Corrections, seen); err != nil {
				return Manifest{}, err
			}
			continue
		}
		if !strings.Contains(line, "=") {
			continue
		}
		key, val := splitKV(line)
		if !allowedKeys[key] {
			return Manifest{}, fmt.Errorf("unknown manifest key: %s", key)
		}
		seen[key]++
		if seen[key] > 1 {
			return Manifest{}, fmt.Errorf("duplicate manifest key: %s", key)
		}
		val = strings.Trim(val, "\"")
		switch key {
		case "manifest_version":
			if val != "2" {
				return Manifest{}, fmt.Errorf("unsupported manifest_version: %s", val)
			}
		case "orchard_id":
			m.OrchardID = val
		case "profile":
			m.Profile = val
		case "sensor_registry":
			m.SensorRegistry = val
		case "state_policy":
			m.StatePolicy = val
		}
	}

	if seen["manifest_version"] == 0 || seen["profile"] == 0 || seen["sensor_registry"] == 0 || seen["readings"] == 0 {
		return Manifest{}, fmt.Errorf("missing required manifest field")
	}
	if len(m.Readings) == 0 {
		return Manifest{}, fmt.Errorf("readings requires at least one file")
	}
	if m.Corrections == nil {
		m.Corrections = []string{}
	}
	return m, nil
}

func parseArrayLine(line, key string, out *[]string, seen map[string]int) error {
	if !allowedKeys[key] {
		return fmt.Errorf("unknown manifest key: %s", key)
	}
	seen[key]++
	if seen[key] > 1 {
		return fmt.Errorf("duplicate manifest key: %s", key)
	}
	idx := strings.Index(line, "[")
	if idx < 0 {
		return fmt.Errorf("malformed manifest array: %s", key)
	}
	inner := strings.TrimSpace(line[idx+1 : len(line)-1])
	if inner == "" {
		*out = []string{}
		return nil
	}
	parts := strings.Split(inner, ",")
	for _, p := range parts {
		p = strings.TrimSpace(p)
		p = strings.Trim(p, "\"'")
		p = strings.TrimSuffix(p, "]")
		if p != "" {
			*out = append(*out, p)
		}
	}
	return nil
}

func splitKV(line string) (string, string) {
	parts := strings.SplitN(line, "=", 2)
	return strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
}

func (m Manifest) Resolve(rel string) (string, error) {
	if filepath.IsAbs(rel) {
		return "", fmt.Errorf("absolute paths not allowed: %s", rel)
	}
	clean := filepath.Clean(rel)
	if strings.HasPrefix(clean, "..") {
		return "", fmt.Errorf("path escapes manifest directory: %s", rel)
	}
	resolved := filepath.Join(m.Dir, clean)
	manifestRoot, _ := filepath.Abs(m.Dir)
	absResolved, err := filepath.Abs(resolved)
	if err != nil {
		return "", err
	}
	fixtureRoot := "/app/environment/fixtures"
	absFixture, _ := filepath.Abs(fixtureRoot)
	underManifest := strings.HasPrefix(absResolved, manifestRoot+string(os.PathSeparator)) || absResolved == manifestRoot
	underFixture := strings.HasPrefix(absResolved, absFixture+string(os.PathSeparator)) || absResolved == absFixture
	if !underManifest && !underFixture {
		return "", fmt.Errorf("path outside allowed roots: %s", rel)
	}
	return resolved, nil
}

func (m Manifest) HashParts() ([][]byte, []string, error) {
	var parts [][]byte
	var paths []string
	parts = append(parts, m.Raw)
	paths = append(paths, m.Path)

	add := func(rel string) error {
		p, err := m.Resolve(rel)
		if err != nil {
			return err
		}
		b, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		parts = append(parts, b)
		paths = append(paths, p)
		return nil
	}
	if err := add(m.Profile); err != nil {
		return nil, nil, err
	}
	if err := add(m.SensorRegistry); err != nil {
		return nil, nil, err
	}
	for _, r := range m.Readings {
		if err := add(r); err != nil {
			return nil, nil, err
		}
	}
	for _, c := range m.Corrections {
		if err := add(c); err != nil {
			return nil, nil, err
		}
	}
	return parts, paths, nil
}
