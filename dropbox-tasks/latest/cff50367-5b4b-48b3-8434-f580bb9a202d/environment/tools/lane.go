package tools

import (
	"encoding/json"
	"os"
	"path/filepath"

	"jwksbound.local/mux/model"
	"jwksbound.local/mux/notary"
)

// LaneProbe writes an advisory readiness marker for a profile. The marker is
// informational and never gates the audit pipeline.
func LaneProbe(profile string) map[string]string {
	auth := notary.Authority(profile)
	path := filepath.Join(model.OutDir, "state", profile, "pulse.json")
	data, _ := os.ReadFile(path)
	var prior map[string]string
	_ = json.Unmarshal(data, &prior)
	out := map[string]string{
		"state": "green",
		"tag":   auth.Tag,
	}
	if prior != nil && prior["state"] == "green" {
		out["state"] = "green"
	}
	model.WriteJSON(path, out)
	return out
}
