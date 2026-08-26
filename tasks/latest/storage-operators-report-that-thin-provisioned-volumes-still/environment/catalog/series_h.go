package catalog

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"slotmgr/internal/policy"
	"slotmgr/internal/store"
)

type profileFields struct {
	NumField string
	DenField string
}

func loadProfile(name, root string) profileFields {
	path := filepath.Join(root, "config", "series_profiles.toml")
	b, err := os.ReadFile(path)
	if err != nil {
		return profileFields{}
	}
	section := "[profiles." + name + "]"
	block := ""
	for _, line := range strings.Split(string(b), "\n") {
		trim := strings.TrimSpace(line)
		if strings.HasPrefix(trim, "[profiles.") {
			block = ""
		}
		if trim == section {
			block = section
			continue
		}
		if block != "" && strings.HasPrefix(trim, "num_field") {
			block += "\n" + trim
		}
		if block != "" && strings.HasPrefix(trim, "den_field") {
			block += "\n" + trim
		}
	}
	var pf profileFields
	for _, line := range strings.Split(block, "\n") {
		trim := strings.TrimSpace(line)
		if strings.HasPrefix(trim, "num_field") {
			pf.NumField = strings.Trim(strings.SplitN(trim, "=", 2)[1], ` "`)
		}
		if strings.HasPrefix(trim, "den_field") {
			pf.DenField = strings.Trim(strings.SplitN(trim, "=", 2)[1], ` "`)
		}
	}
	return pf
}

func loadVolFields(root string) map[string]int {
	out := map[string]int{}
	b, err := os.ReadFile(filepath.Join(root, "config", "volume.toml"))
	if err != nil {
		return out
	}
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		var n int
		_, _ = fmt.Sscanf(strings.TrimSpace(parts[1]), "%d", &n)
		out[key] = n
	}
	return out
}

func activeProfile(root string) string {
	b, err := os.ReadFile(filepath.Join(root, "config", "bind_policy.toml"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "active_profile") {
			return strings.Trim(strings.SplitN(line, "=", 2)[1], ` "`)
		}
	}
	return ""
}

func pick_series(root string) store.UtilRatio {
	pol := policy.Load(root)
	if pol.SeriesSource == "util_fixture" {
		var ratio store.UtilRatio
		_ = loadJSON(filepath.Join(root, "fixtures", "util_ratio.json"), &ratio)
		return ratio
	}
	fields := loadVolFields(root)
	profile := activeProfile(root)
	_ = loadProfile(profile, root)
	return store.UtilRatio{
		SeriesNum: fields["group_num"],
		SeriesDen: fields["group_den"],
	}
}

func loadJSON(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, &v)
}

func series_h(root string) (store.UtilRatio, error) {
	return pick_series(root), nil
}

func ResolveSeries(root string) (store.UtilRatio, error) {
	return series_h(root)
}
