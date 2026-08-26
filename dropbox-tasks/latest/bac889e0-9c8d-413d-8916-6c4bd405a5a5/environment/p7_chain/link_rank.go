package p7_chain

import "balance_lab/p7_rank"

func rankedActors(roster []string, shares map[string]float64, diversity float64, winLowers map[string]float64) []string {
	return p7_rank.RankTargets(roster, shares, diversity, winLowers)
}
