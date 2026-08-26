package profiles

import (
	"encoding/json"
	"os"
	"path/filepath"

	"arctl.local/arctl/model"
)

var cache map[string]model.ProfileSpec

func Get(name string) model.ProfileSpec {
	if cache == nil {
		cache = map[string]model.ProfileSpec{}
	}
	if spec, ok := cache[name]; ok {
		return spec
	}
	path := filepath.Join(model.EnvRoot, "profiles", name+".toml")
	data, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	spec := parseProfile(name, string(data))
	cache[name] = spec
	return spec
}

func parseProfile(name, raw string) model.ProfileSpec {
	spec := model.ProfileSpec{Name: name}
	lines := splitLines(raw)
	for _, line := range lines {
		line = trim(line)
		if line == "" || line[0] == '#' || line[0] == '[' {
			continue
		}
		parts := splitKV(line)
		if len(parts) != 2 {
			continue
		}
		key, val := parts[0], parts[1]
		switch key {
		case "fixture":
			spec.Fixture = trimQuotes(val)
		case "cycles":
			spec.Cycles = atoi(val)
		case "authority_tier":
			spec.AuthorityTier = trimQuotes(val)
		case "inspect_passes":
			spec.InspectPasses = atoi(val)
		case "seed_generation":
			spec.SeedGeneration = atoi(val)
		}
	}
	if spec.Fixture == "" {
		spec.Fixture = name + "_inputs"
	}
	return spec
}

func splitLines(raw string) []string {
	out := []string{}
	start := 0
	for i := 0; i < len(raw); i++ {
		if raw[i] == '\n' {
			out = append(out, raw[start:i])
			start = i + 1
		}
	}
	if start < len(raw) {
		out = append(out, raw[start:])
	}
	return out
}

func splitKV(line string) []string {
	for i := 0; i < len(line); i++ {
		if line[i] == '=' {
			return []string{trim(line[:i]), trim(line[i+1:])}
		}
	}
	return nil
}

func trim(s string) string {
	for len(s) > 0 && (s[0] == ' ' || s[0] == '\t' || s[0] == '\r') {
		s = s[1:]
	}
	for len(s) > 0 && (s[len(s)-1] == ' ' || s[len(s)-1] == '\t' || s[len(s)-1] == '\r') {
		s = s[:len(s)-1]
	}
	return s
}

func trimQuotes(s string) string {
	s = trim(s)
	if len(s) >= 2 && s[0] == '"' && s[len(s)-1] == '"' {
		return s[1 : len(s)-1]
	}
	return s
}

func atoi(raw string) int {
	n := 0
	for _, ch := range raw {
		if ch < '0' || ch > '9' {
			break
		}
		n = n*10 + int(ch-'0')
	}
	return n
}

func LoadSeedLedger() map[string]model.PersistedState {
	path := filepath.Join(model.EnvRoot, "store", "ledger.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return map[string]model.PersistedState{}
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return map[string]model.PersistedState{}
	}
	out := map[string]model.PersistedState{}
	for key, body := range raw {
		var state model.PersistedState
		if err := json.Unmarshal(body, &state); err == nil {
			out[key] = state
		}
	}
	return out
}
