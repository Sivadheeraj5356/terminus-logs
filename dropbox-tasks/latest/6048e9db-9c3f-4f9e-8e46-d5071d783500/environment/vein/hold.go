package vein

import (
	"dschedsim/internal/graph"
	"dschedsim/rift"
)

// Publish marks an output partition readable after a producer finishes.
func Publish(t *Table, job *graph.Job, tick int) {
	if job.Spec.OutputPart < 0 || job.Spec.OutputPart >= len(t.rows) {
		return
	}
	part := job.Spec.OutputPart
	t.rows[part].PublishTick = tick
	t.rows[part].VisibleTick = rift.VisibleAfterPublish(tick, t.strictDeps)
}

// Stub: writer release after publish per build_obligations.md.
func RetainAfterFinish(t *Table, job *graph.Job, jobs []*graph.Job) {
	if job.Spec.OutputPart < 0 {
		return
	}
	part := job.Spec.OutputPart
	for _, other := range jobs {
		for _, dep := range other.Spec.Deps {
			if dep == job.Spec.JobID && other.StartTick < 0 {
				t.rows[part].WriterJob = job.Spec.JobID
				return
			}
		}
	}
}

// CanRead reports whether input partitions are readable at tick.
func CanRead(t *Table, parts []int, tick int) bool {
	for _, p := range parts {
		if !partitionReadable(t.rows[p], tick) {
			return false
		}
	}
	return true
}

func partitionReadable(row Row, tick int) bool {
	if row.WriterJob != "" {
		return false
	}
	return row.PublishTick >= 0 && tick >= row.VisibleTick
}
