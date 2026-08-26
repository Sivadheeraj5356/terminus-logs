package decoy

import "dschedsim/internal/graph"

// ProbeDepth is a diagnostic helper for queue inspection tooling.
func ProbeDepth(jobs []*graph.Job) int {
	n := 0
	for _, j := range jobs {
		if j.Queued && j.StartTick < 0 {
			n++
		}
	}
	return n
}
