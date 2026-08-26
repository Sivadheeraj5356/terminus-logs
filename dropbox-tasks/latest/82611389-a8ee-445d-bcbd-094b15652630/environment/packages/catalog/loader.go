package catalog

import (
	"encoding/csv"
	"fmt"
	"os"
	"strings"
)

type Module struct {
	ID      string
	Version string
	Depends []string
}

func LoadManifest(path string) ([]Module, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	rows, err := csv.NewReader(f).ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) < 2 {
		return nil, fmt.Errorf("manifest empty")
	}

	var out []Module
	for _, row := range rows[1:] {
		if len(row) < 3 {
			continue
		}
		deps := []string{}
		raw := strings.TrimSpace(row[2])
		if raw != "" {
			for _, dep := range strings.Split(raw, ",") {
				dep = strings.TrimSpace(dep)
				if dep != "" {
					deps = append(deps, dep)
				}
			}
		}
		out = append(out, Module{
			ID:      strings.TrimSpace(row[0]),
			Version: strings.TrimSpace(row[1]),
			Depends: deps,
		})
	}
	return out, nil
}

func Index(modules []Module) map[string]Module {
	out := make(map[string]Module, len(modules))
	for _, m := range modules {
		out[m.ID] = m
	}
	return out
}
