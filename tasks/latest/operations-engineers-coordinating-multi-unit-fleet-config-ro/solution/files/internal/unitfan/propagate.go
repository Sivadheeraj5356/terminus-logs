package unitfan

import (
	"sort"

	"odip/internal/scenpack"
)

type ImpactRow struct {
	DecisionID    string   `json:"decision_id"`
	AffectedUnits []string `json:"affected_units"`
	ImpactScore   int      `json:"impact_score"`
}

func FanOut(decisions []scenpack.Decision, topo []scenpack.TopoEdge) []ImpactRow {
	children := map[string][]string{}
	for _, e := range topo {
		children[e.Parent] = append(children[e.Parent], e.Child)
	}
	for k := range children {
		sort.Strings(children[k])
	}
	rows := make([]ImpactRow, 0, len(decisions))
	for _, d := range decisions {
		seen := map[string]bool{}
		stack := append([]string(nil), d.DirectUnits...)
		for len(stack) > 0 {
			u := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			if seen[u] {
				continue
			}
			seen[u] = true
			for _, c := range children[u] {
				if !seen[c] {
					stack = append(stack, c)
				}
			}
		}
		units := make([]string, 0, len(seen))
		for u := range seen {
			units = append(units, u)
		}
		sort.Strings(units)
		rows = append(rows, ImpactRow{
			DecisionID:    d.ID,
			AffectedUnits: units,
			ImpactScore:   len(units),
		})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].DecisionID < rows[j].DecisionID })
	return rows
}
