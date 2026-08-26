package harness

import (
	"encoding/json"
	"os"

	"chronctl/internal/policy"
	"chronctl/internal/sim"
	"chronctl/pkg/api"
)

const rotatePath = "/app/config/rotate_schedule.json"

func loadRotate() *policy.Schedule {
	sc, err := policy.ReadTab(rotatePath)
	if err != nil {
		return &policy.Schedule{GenesisPrior: "genesis"}
	}
	return sc
}

func RunPack(pack *api.Pack) (*api.Report, error) {
	sched := loadRotate()
	prior := "genesis"
	if sched != nil && sched.GenesisPrior != "" {
		prior = sched.GenesisPrior
	}
	cum := 0
	report := &api.Report{SchemaVersion: 1}
	for i := range pack.Scenarios {
		row := sim.WorkA(&pack.Scenarios[i], prior, cum, sched)
		report.Scenarios = append(report.Scenarios, row)
		prior = row.TimelineHeadHex
		cum += row.EventsReplayed
	}
	return report, nil
}

func WriteReport(path string, report *api.Report) error {
	raw, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}
