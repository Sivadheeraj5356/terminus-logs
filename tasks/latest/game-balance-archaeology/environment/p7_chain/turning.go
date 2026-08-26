package p7_chain

import (
	"math"

	"balance_lab/p9_types"
)

func patchVector(patchID string, matches []p9_types.MatchRow, roster []string) map[string]float64 {
	totals := map[string]int{}
	for _, actor := range roster {
		totals[actor] = 0
	}
	for _, row := range matches {
		if row.PatchID != patchID {
			continue
		}
		totals[row.Actor] += row.Picks
	}
	vec := map[string]float64{}
	for _, actor := range roster {
		vec[actor] = actorShare(totals[actor], len(roster))
	}
	return vec
}

func BuildTurningPoints(rows []p9_types.ChronologyRow, matches []p9_types.MatchRow, roster []string, threshold float64) []p9_types.TurningPoint {
	ordered := append([]p9_types.ChronologyRow(nil), rows...)
	for i := 0; i < len(ordered); i++ {
		for j := i + 1; j < len(ordered); j++ {
			if ordered[j].Seq < ordered[i].Seq {
				ordered[i], ordered[j] = ordered[j], ordered[i]
			}
		}
	}
	var points []p9_types.TurningPoint
	for i := 0; i < len(ordered)-1; i++ {
		va := patchVector(ordered[i].PatchID, matches, roster)
		vb := patchVector(ordered[i+1].PatchID, matches, roster)
		score := shiftBetween(va, vb, roster)
		if score >= threshold {
			points = append(points, p9_types.TurningPoint{
				PatchID:    ordered[i+1].PatchID,
				ShiftScore: math.Round(score*10000) / 10000,
			})
		}
	}
	if points == nil {
		return []p9_types.TurningPoint{}
	}
	return points
}
