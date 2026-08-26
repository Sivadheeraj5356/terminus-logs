package p7_chain

import "balance_lab/p9_types"

func BuildRecommendations(lastEra p9_types.EraSpan, rows []p9_types.ChronologyRow, matches []p9_types.MatchRow, notes []p9_types.NoteRow, roster []string, z float64) []p9_types.Recommendation {
	totals := eraTotals(lastEra, rows, matches)
	totalPicks := 0
	for _, actor := range roster {
		totalPicks += totals[actor].Picks
	}
	_ = totalPicks
	shares := map[string]float64{}
	var positive []float64
	for _, actor := range roster {
		picks := totals[actor].Picks
		share := actorShare(picks, len(roster))
		shares[actor] = share
		if picks > 0 {
			positive = append(positive, share)
		}
	}
	diversity := eraDiversity(positive)
	winLowers := map[string]float64{}
	for _, actor := range roster {
		winLowers[actor] = actorWinLower(totals[actor].Wins, totals[actor].Picks, z)
	}
	ranked := rankedActors(roster, shares, diversity, winLowers)
	out := make([]p9_types.Recommendation, len(ranked))
	for i, actor := range ranked {
		out[i] = p9_types.Recommendation{
			Actor:        actor,
			Priority:     i + 1,
			RationaleTag: actorRationale(actor, notes, rows),
		}
	}
	return out
}
