package tabulate

import "plangen/internal/model"

// Coverage reports how many equal-width cells the fold populates. It is a
// diagnostic aid and does not take part in fitting.
func Coverage(rows []model.Row, unit, cells int) int {
	seen := make([]bool, cells)
	for _, r := range rows {
		seen[cellOf(r.Raw, unit, cells)] = true
	}
	n := 0
	for _, s := range seen {
		if s {
			n++
		}
	}
	return n
}
