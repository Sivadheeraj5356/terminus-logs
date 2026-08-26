package vein

import "dschedsim/internal/graph"

// ReserveOnSubmit is a no-op at submit time.
func ReserveOnSubmit(t *Table, job *graph.Job) {
	_ = t
	_ = job
}
