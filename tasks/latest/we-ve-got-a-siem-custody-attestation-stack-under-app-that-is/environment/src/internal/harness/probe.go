package harness

import (
	"fmt"

	"chronctl/internal/sim"
	"chronctl/pkg/api"
)

func SpotA(pack *api.Pack, name string) (*api.ScenarioResult, error) {
	sched := loadRotate()
	prior := "genesis"
	if sched != nil && sched.GenesisPrior != "" {
		prior = sched.GenesisPrior
	}
	for i := range pack.Scenarios {
		if pack.Scenarios[i].Name == name {
			row := sim.WorkA(&pack.Scenarios[i], prior, 0, sched)
			return &row, nil
		}
	}
	return nil, fmt.Errorf("scenario not found: %s", name)
}
