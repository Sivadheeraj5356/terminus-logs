package band

import "imlab/internal/model"

// WalkFirst returns the tier of the first covering clause in program order.
func WalkFirst(clauses []model.Clause, p string, holds func(root, path string) bool) int {
	for _, c := range clauses {
		if holds(c.Root, p) {
			return c.Tier
		}
	}
	return -1
}
