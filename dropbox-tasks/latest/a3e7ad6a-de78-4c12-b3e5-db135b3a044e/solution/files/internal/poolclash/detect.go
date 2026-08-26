package poolclash

import (
	"sort"

	"odip/internal/planwrite"
)

func FindConflicts(lat *planwrite.Lattice) []planwrite.Conflict {
	out := []planwrite.Conflict{}
	books := lat.ResourceBookings
	for i := 0; i < len(books); i++ {
		for j := i + 1; j < len(books); j++ {
			a, b := books[i], books[j]
			if a.Pool != b.Pool || a.DecisionID == b.DecisionID {
				continue
			}
			if a.Start < b.End && b.Start < a.End {
				da, db := a.DecisionID, b.DecisionID
				if da > db {
					da, db = db, da
				}
				out = append(out, planwrite.Conflict{
					Type: "resource", Pool: a.Pool, DecisionA: da, DecisionB: db,
				})
			}
		}
	}
	affected := map[string][]string{}
	for _, row := range lat.ImpactRows {
		affected[row.DecisionID] = row.AffectedUnits
	}
	ids := append([]string(nil), lat.DecisionIDs...)
	sort.Strings(ids)
	for i := 0; i < len(ids); i++ {
		for j := i + 1; j < len(ids); j++ {
			a, b := ids[i], ids[j]
			if !lat.Exclusive[a] || !lat.Exclusive[b] {
				continue
			}
			wa, wb := lat.Windows[a], lat.Windows[b]
			if !(wa.Start < wb.End && wb.Start < wa.End) {
				continue
			}
			setB := map[string]bool{}
			for _, u := range affected[b] {
				setB[u] = true
			}
			shared := []string{}
			for _, u := range affected[a] {
				if setB[u] {
					shared = append(shared, u)
				}
			}
			sort.Strings(shared)
			for _, u := range shared {
				out = append(out, planwrite.Conflict{
					Type: "timeline", Unit: u, DecisionA: a, DecisionB: b,
				})
			}
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Type != out[j].Type {
			return out[i].Type < out[j].Type
		}
		ki := out[i].Pool
		if ki == "" {
			ki = out[i].Unit
		}
		kj := out[j].Pool
		if kj == "" {
			kj = out[j].Unit
		}
		if ki != kj {
			return ki < kj
		}
		if out[i].DecisionA != out[j].DecisionA {
			return out[i].DecisionA < out[j].DecisionA
		}
		return out[i].DecisionB < out[j].DecisionB
	})
	return out
}
