package report

import (
	"math"
	"sort"
)

func BuildSummary(rows []SessionRow) Summary {
	total := len(rows)
	clean := 0
	pulls := 0
	anomalies := 0
	for _, r := range rows {
		if r.Status == "clean" {
			clean++
		}
		pulls += r.PullsKept
		anomalies += len(r.Anomalies)
	}
	tainted := total - clean
	score := 0.0
	if total > 0 {
		// Risk coverage: tainted / total
		score = round2(100.0 * float64(tainted) / float64(total))
	}
	return Summary{
		SessionsTotal:   total,
		SessionsClean:   clean,
		SessionsTainted: tainted,
		PullsTotal:      pulls,
		AnomalyCount:    anomalies,
		IntegrityScore:  score,
	}
}

func SortRows(rows []SessionRow) {
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].PlayerID != rows[j].PlayerID {
			return rows[i].PlayerID < rows[j].PlayerID
		}
		return rows[i].SessionID < rows[j].SessionID
	})
}

func CleanIDs(rows []SessionRow) []string {
	out := []string{}
	for _, r := range rows {
		if r.Status == "clean" {
			out = append(out, r.SessionID)
		}
	}
	sort.Strings(out)
	return out
}

func round2(v float64) float64 {
	return math.Round(v*100) / 100
}
