package triage

import (
	"sort"

	"splicekit/pkg/model"
)

func rank_w(demands []model.Demand) []model.Demand {
	out := append([]model.Demand(nil), demands...)
	sort.SliceStable(out, func(i, j int) bool {
		pi := out[i].Priority
		pj := out[j].Priority
		if pi != pj {
			return pi > pj
		}
		return out[i].ID > out[j].ID
	})
	return out
}

func Rank(demands []model.Demand) []model.Demand {
	return rank_w(demands)
}
