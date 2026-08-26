package band

import "imlab/internal/model"

// Prefer returns a tier id for path p among covering clauses.
func Prefer(clauses []model.Clause, p string, holds func(root, path string) bool) int {
	bestLen := -1
	bestTier := -1
	for _, c := range clauses {
		if !holds(c.Root, p) {
			continue
		}
		n := len(c.Root)
		if n > bestLen || (n == bestLen && c.Tier > bestTier) {
			bestLen = n
			bestTier = c.Tier
		}
	}
	return bestTier
}

func verbKnown(verbs []int, v int) bool {
	for _, x := range verbs {
		if x == v {
			return true
		}
	}
	return false
}

// BitsAt returns verb bits active at tier t for path p.
func BitsAt(clauses []model.Clause, tier int, p string, holds func(root, path string) bool) []int {
	for _, c := range clauses {
		if c.Tier != tier || !holds(c.Root, p) {
			continue
		}
		return []int{c.Verb}
	}
	return nil
}
