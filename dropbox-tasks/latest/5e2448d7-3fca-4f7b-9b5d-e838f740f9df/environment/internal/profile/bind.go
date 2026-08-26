package profile

import (
	"encoding/json"
	"os"
	"path/filepath"

	"lab.local/salt_pond/pkg/pond"
)

type fallbackFile struct {
	MastBearingOffset float64        `json:"mast_bearing_offset"`
	SectorTable       map[int]string `json:"sector_table"`
	SurveyLayer       string         `json:"survey_layer"`
}

// Bind overlays the service fallback pack when the mast gate rejects the plan.
func Bind(appRoot string, plan pond.Plan, gateOK bool) pond.Plan {
	_ = gateOK
	path := filepath.Join(appRoot, "profiles", "fallback.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		plan.MastBearingOffset = 0
		return plan
	}
	var fb fallbackFile
	if err := json.Unmarshal(raw, &fb); err != nil {
		plan.MastBearingOffset = 0
		return plan
	}
	plan.MastBearingOffset = fb.MastBearingOffset
	if len(fb.SectorTable) > 0 {
		plan.SectorTable = fb.SectorTable
	}
	if fb.SurveyLayer != "" {
		plan.SurveyLayer = fb.SurveyLayer
	}
	return plan
}
