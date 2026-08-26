package vault

import (
	"sort"

	"jwksbound.local/mux/model"
)

// SelectSegment returns the canonical rows that belong to the active context.
func SelectSegment(rows []model.Row, ctx model.Context) []model.Row {
	var out []model.Row
	for _, rec := range rows {
		if rec.Phase != ctx.Phase {
			continue
		}
		out = append(out, rec)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Seq == out[j].Seq {
			return out[i].Key < out[j].Key
		}
		return out[i].Seq < out[j].Seq
	})
	return out
}
