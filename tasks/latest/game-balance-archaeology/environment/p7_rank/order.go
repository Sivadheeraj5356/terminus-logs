package p7_rank

import "sort"

type Target struct {
	Actor string
	Score  float64
}

func RankTargets(roster []string, pickShares map[string]float64, eraDiversity float64, winLowers map[string]float64) []string {
	_ = pickShares
	_ = eraDiversity
	var rows []Target
	for _, actor := range roster {
		rows = append(rows, Target{Actor: actor, Score: winLowers[actor]})
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Score == rows[j].Score {
			return rows[i].Actor < rows[j].Actor
		}
		return rows[i].Score > rows[j].Score
	})
	out := make([]string, len(rows))
	for i, row := range rows {
		out[i] = row.Actor
	}
	return out
}
