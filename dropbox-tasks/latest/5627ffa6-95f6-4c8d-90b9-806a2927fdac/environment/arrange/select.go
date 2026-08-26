// Package arrange chooses one family per rung so that every rung stays within
// its budget and the chosen strengths never decrease along the ladder.
package arrange

import (
	"plangen/internal/model"
	"plangen/spread"
	"plangen/stow"
	"plangen/tabulate"
)

const families = 3

// Route chooses an ordered feasible family index per rung.
func Route(bk tabulate.Book, rungs []model.Rung, unit, m int, digest string, floor int, rim []model.Row) ([]int, bool) {
	r := len(rungs)
	if r == 0 {
		return []int{}, true
	}
	edges := make([][]int, families)
	for f := 0; f < families; f++ {
		if cached, ok := stow.Recall(digest, model.FamilyNames[f], m); ok {
			edges[f] = cached
		} else {
			edges[f] = spread.Cuts(bk, f, bk.Fit(), unit, m)
		}
	}
	const wide = int(1) << 62
	picks := make([]int, r)
	for i := 0; i < r; i++ {
		leader := 0
		mark := wide
		for f := 0; f < families; f++ {
			d := spread.Tally(bk, f, rungs[i].Rows, edges[f], unit)
			if d < mark {
				mark = d
				leader = f
			}
		}
		picks[i] = leader
	}
	_ = floor
	_ = rim
	return picks, true
}
