package p7_chain

import (
	"math"

	"balance_lab/p9_types"
)

func BuildEras(rows []p9_types.ChronologyRow, matches []p9_types.MatchRow, roster []string, gap int, z float64) []p9_types.EraOut {
	spans := eraSpans(rows, gap)
	out := make([]p9_types.EraOut, 0, len(spans))
	for _, era := range spans {
		totals := eraTotals(era, rows, matches)
		var shares []float64
		dominant := roster[0]
		bestShare := -1.0
		for _, actor := range roster {
			picks := totals[actor].Picks
			share := actorShare(picks, len(roster))
			if picks > 0 {
				shares = append(shares, share)
			}
			if share > bestShare {
				bestShare = share
				dominant = actor
			}
		}
		domWins := totals[dominant].Wins
		domPicks := totals[dominant].Picks
		out = append(out, p9_types.EraOut{
			ID:               era.ID,
			StartPatch:       era.StartPatch,
			EndPatch:         era.EndPatch,
			DominantActor:    dominant,
			DiversityIndex:   math.Round(eraDiversity(shares)*10000) / 10000,
			DominantWinLower: math.Round(actorWinLower(domWins, domPicks, z)*10000) / 10000,
		})
	}
	return out
}
