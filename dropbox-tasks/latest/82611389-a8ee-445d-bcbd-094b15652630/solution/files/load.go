package config

import (
	"bufio"
	"os"
	"strings"
)

type Policy struct {
	RequireRegistryApproval bool
	DebugEndpointsEnabled   bool
	MinModuleVersions       map[string]string
	FleetReleasePin         string
}

func Load(path string) (Policy, error) {
	f, err := os.Open(path)
	if err != nil {
		return Policy{}, err
	}
	defer f.Close()

	cfg := Policy{
		RequireRegistryApproval: true,
		DebugEndpointsEnabled:   false,
		MinModuleVersions: map[string]string{
			"billing-api":   "2.0.0",
			"ingest-worker": "1.1.0",
		},
		FleetReleasePin: "fleet-2025.11.4",
	}

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		switch key {
		case "require_registry_approval":
			cfg.RequireRegistryApproval = strings.EqualFold(val, "true")
		case "debug_endpoints_enabled":
			cfg.DebugEndpointsEnabled = strings.EqualFold(val, "true")
		case "fleet_release_pin":
			cfg.FleetReleasePin = val
		case "min_module_versions":
			cfg.MinModuleVersions = parseMinVersions(val)
		}
	}
	return cfg, sc.Err()
}

func parseMinVersions(raw string) map[string]string {
	out := map[string]string{}
	for _, pair := range strings.Split(raw, ",") {
		pair = strings.TrimSpace(pair)
		if pair == "" {
			continue
		}
		kv := strings.SplitN(pair, ":", 2)
		if len(kv) != 2 {
			continue
		}
		out[strings.TrimSpace(kv[0])] = strings.TrimSpace(kv[1])
	}
	return out
}
