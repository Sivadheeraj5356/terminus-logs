package quorum

import (
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/notary"
)

func Floor(profile string) int {
	layout := notary.ReadLayout()
	meta := layout[profile]
	return meta.GenerationFloor
}

// Active keeps canonical rows eligible for phase reconciliation.
func Active(rows []model.Row, floor int) []model.Row {
	var out []model.Row
	for _, rec := range rows {
		if rec.Generation > floor {
			out = append(out, rec)
		}
	}
	return out
}
