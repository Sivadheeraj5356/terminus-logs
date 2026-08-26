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

// RetainAfterFinish clears writer leases once outputs are published.
func RetainAfterFinish(t *Table, job *graph.Job, jobs []*graph.Job) {
	_ = jobs
	releasePublishedWriter(t, job)
}

func releasePublishedWriter(t *Table, job *graph.Job) {
	if job == nil || job.Spec.OutputPart < 0 {
		return
	}
	if job.Spec.OutputPart >= len(t.rows) {
		return
	}
	part := job.Spec.OutputPart
	row := &t.rows[part]
	if row.PublishTick < 0 {
		return
	}
	row.WriterJob = ""
}

// CanRead reports whether input partitions are readable at tick.
func CanRead(t *Table, parts []int, tick int) bool {
	for _, p := range parts {
		if p < 0 || p >= len(t.rows) {
			return false
		}
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
	if row.PublishTick < 0 {
		return false
	}
	return tick >= row.VisibleTick
}
