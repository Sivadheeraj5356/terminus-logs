package policy

import (
	"encoding/json"
	"os"
)

type Threshold struct {
	AfterEvents int `json:"after_events"`
	EpochBump   int `json:"epoch_bump"`
}

type Schedule struct {
	Revision     string      `json:"revision"`
	GenesisPrior string      `json:"genesis_prior"`
	Thresholds   []Threshold `json:"thresholds"`
}

func ReadTab(path string) (*Schedule, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var sc Schedule
	if err := json.Unmarshal(raw, &sc); err != nil {
		return nil, err
	}
	return &sc, nil
}

func BumpFor(sc *Schedule, packEventsBefore int) int {
	if sc == nil {
		return 0
	}
	for _, th := range sc.Thresholds {
		if packEventsBefore >= th.AfterEvents {
			return th.EpochBump
		}
	}
	return 0
}

func SeedTok(sc *Schedule) string {
	if sc == nil || sc.GenesisPrior == "" {
		return "genesis"
	}
	return sc.GenesisPrior
}
