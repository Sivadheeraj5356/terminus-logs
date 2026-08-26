package simdrive

import (
	"os"
	"path/filepath"
)

type ScenarioSpec struct {
	Name      string
	ColdFirst bool
	Seed      int
}

func LoadScenario(envRoot, name string) (ScenarioSpec, error) {
	switch name {
	case "wp-maint":
		return ScenarioSpec{Name: name, ColdFirst: false, Seed: 1}, nil
	default:
		return ScenarioSpec{}, os.ErrNotExist
	}
}

func ScenarioConfigPath(envRoot, name string) string {
	return filepath.Join(envRoot, "configs", "scenarios", name+".toml")
}
