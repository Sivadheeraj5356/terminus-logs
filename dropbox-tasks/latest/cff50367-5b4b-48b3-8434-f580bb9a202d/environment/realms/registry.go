package realms

import (
	"os"
	"path/filepath"
	"strings"

	"jwksbound.local/mux/model"
)

// Lookup loads a profile spec from its TOML descriptor.
func Lookup(name string) model.ProfileSpec {
	base := filepath.Join(model.EnvRoot, "realms", name+".toml")
	data, err := os.ReadFile(base)
	if err != nil {
		panic(err)
	}
	spec := model.ProfileSpec{
		Name:       name,
		FixtureDir: filepath.Join(model.EnvRoot, "fixtures", name+"_scopes"),
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "runs = ") {
			inner := strings.Trim(strings.TrimPrefix(line, "runs = "), "[]")
			for _, part := range strings.Split(inner, ",") {
				part = strings.Trim(strings.TrimSpace(part), "\"")
				if part != "" {
					spec.Runs = append(spec.Runs, part)
				}
			}
		}
	}
	return spec
}
