package arrange

import "plangen/internal/model"

// Summarize returns the row count of each rung. It records completed-run shape
// for diagnostics and never participates in selection.
func Summarize(rungs []model.Rung) []int {
	out := make([]int, 0, len(rungs))
	for _, r := range rungs {
		out = append(out, len(r.Rows))
	}
	return out
}
