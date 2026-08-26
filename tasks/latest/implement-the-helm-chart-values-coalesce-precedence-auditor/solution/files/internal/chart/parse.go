package chart

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"helm-chart-coalesce/internal/yamlmini"
)

func LoadChart(dir string) (Chart, map[string]any, error) {
	meta, err := parseChartYAML(filepath.Join(dir, "Chart.yaml"))
	if err != nil {
		return Chart{}, nil, err
	}
	defaults := map[string]any{}
	valuesPath := filepath.Join(dir, "values.yaml")
	if _, err := os.Stat(valuesPath); err == nil {
		raw, err := os.ReadFile(valuesPath)
		if err != nil {
			return Chart{}, nil, err
		}
		defaults, err = yamlmini.Parse(string(raw))
		if err != nil {
			return Chart{}, nil, err
		}
	}
	return meta, defaults, nil
}

func parseChartYAML(path string) (Chart, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Chart{}, err
	}
	doc, err := yamlmini.Parse(string(raw))
	if err != nil {
		return Chart{}, err
	}
	name, _ := doc["name"].(string)
	version, _ := doc["version"].(string)
	if name == "" {
		return Chart{}, fmt.Errorf("chart missing name")
	}
	c := Chart{Name: name, Version: version}
	depsAny, ok := doc["dependencies"]
	if !ok {
		return c, nil
	}
	list, ok := depsAny.([]any)
	if !ok {
		return Chart{}, fmt.Errorf("dependencies must be a list")
	}
	for _, item := range list {
		m, ok := item.(map[string]any)
		if !ok {
			return Chart{}, fmt.Errorf("dependency entry must be a map")
		}
		dep := Dependency{
			Name:    str(m["name"]),
			Version: str(m["version"]),
		}
		dep.Condition = str(m["condition"])
		dep.Alias = str(m["alias"])
		if dep.Name == "" {
			return Chart{}, fmt.Errorf("dependency missing name")
		}
		c.Dependencies = append(c.Dependencies, dep)
	}
	return c, nil
}

func LoadValuesFile(path string) (map[string]any, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return yamlmini.Parse(string(raw))
}

func str(v any) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return t
	default:
		return fmt.Sprint(t)
	}
}

func ChartDir(root, depName string) string {
	return filepath.Join(root, "charts", depName)
}

func NormalizePath(p string) string {
	return filepath.ToSlash(p)
}

func SortDeps(deps []Dependency) []Dependency {
	out := append([]Dependency(nil), deps...)
	for i := 0; i < len(out); i++ {
		for j := i + 1; j < len(out); j++ {
			if out[j].ManifestID() < out[i].ManifestID() {
				out[i], out[j] = out[j], out[i]
			}
		}
	}
	return out
}

func SplitChartPrefix(key string) (chartID string, rest string) {
	if !strings.Contains(key, ".") {
		return "", key
	}
	parts := strings.SplitN(key, ".", 2)
	return parts[0], parts[1]
}
