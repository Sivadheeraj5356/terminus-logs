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
	_ = topo
	rows := make([]ImpactRow, 0, len(decisions))
	for _, d := range decisions {
		units := append([]string(nil), d.DirectUnits...)
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
