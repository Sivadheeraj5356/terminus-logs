package band

import "imlab/internal/model"

// RankTier returns the tier whose covering root is longest for path p.
func RankTier(clauses []model.Clause, p string, holds func(root, path string) bool) int {
	bestLen := -1
	bestTier := -1
	for _, c := range clauses {
		if !holds(c.Root, p) {
			continue
		}
		if len(c.Root) > bestLen {
			bestLen = len(c.Root)
			bestTier = c.Tier
		}
	}
	return bestTier
}
