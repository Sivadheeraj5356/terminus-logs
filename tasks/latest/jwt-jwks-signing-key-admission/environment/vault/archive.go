package vault

import (
	"sort"

	"jwksbound.local/mux/model"
)

// InspectArchive returns rows for one run in sequence order. Diagnostics-only.
func InspectArchive(rows []model.Row, ctx model.Context) []model.Row {
	var out []model.Row
	for _, rec := range rows {
		if rec.RunID == ctx.RunID {
			out = append(out, rec)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Seq < out[j].Seq })
	return out
}
