package support

import (
	"encoding/json"
	"os"
)

const customsPath = "/app/var/immunoflow_customs.json"

type CustomsAccrue struct {
	TotalDelayDays int            `json:"total_delay_days"`
	ByRegion       map[string]int `json:"by_region"`
}

func LoadCustoms() CustomsAccrue {
	raw, err := os.ReadFile(customsPath)
	if err != nil {
		return CustomsAccrue{ByRegion: map[string]int{}}
	}
	var c CustomsAccrue
	_ = json.Unmarshal(raw, &c)
	if c.ByRegion == nil {
		c.ByRegion = map[string]int{}
	}
	return c
}

func SaveCustoms(c CustomsAccrue) error {
	raw, _ := json.MarshalIndent(c, "", "  ")
	return os.WriteFile(customsPath, append(raw, '\n'), 0o644)
}
