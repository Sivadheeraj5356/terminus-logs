package vein

import "dschedsim/internal/graph"

// Stub: submit-time output exclusivity per build_obligations.md.
func ReserveOnSubmit(t *Table, job *graph.Job) {
	if job == nil || job.Spec.OutputPart < 0 {
		return
	}
	if job.Spec.OutputPart >= len(t.rows) {
		return
	}
	t.rows[job.Spec.OutputPart].WriterJob = job.Spec.JobID
}
