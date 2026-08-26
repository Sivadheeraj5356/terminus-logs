package thaw

import (
	"dschedsim/drift"
	"dschedsim/internal/graph"
	"dschedsim/placement"
	"dschedsim/slate"
	"dschedsim/vein"
)

type ActiveJob struct {
	Job    *graph.Job
	Remain int
}

func Hydrate(
	view slate.View,
	jobs []*graph.Job,
	byID map[string]*graph.Job,
	table *vein.Table,
	pool *placement.Pool,
	queue *drift.Queue,
	done map[string]bool,
) []ActiveJob {
	for k := range done {
		delete(done, k)
	}
	for _, id := range view.Done {
		done[id] = true
	}

	rows := make([]vein.Row, len(view.LeaseRows))
	copy(rows, view.LeaseRows)
	table.Restore(rows)

	pool.Restore(view.PoolBusy)

	for _, j := range jobs {
		j.ReadyTick = -1
		j.StartTick = -1
		j.FinishTick = -1
		j.QueueWait = 0
		j.Running = false
		j.Queued = false
		j.Node = -1
	}
	for _, jv := range view.Jobs {
		j := byID[jv.JobID]
		if j == nil {
			continue
		}
		j.ReadyTick = jv.ReadyTick
		j.StartTick = jv.StartTick
		j.FinishTick = jv.FinishTick
		j.QueueWait = jv.QueueWait
		j.Running = jv.Running
		j.Queued = jv.Queued
		j.Node = jv.Node
	}

	queue.Clear()
	for _, id := range view.QueueIDs {
		if j := byID[id]; j != nil {
			queue.Enqueue(j)
		}
	}

	var running []ActiveJob
	for _, rv := range view.Running {
		j := byID[rv.JobID]
		if j == nil {
			continue
		}
		running = append(running, ActiveJob{Job: j, Remain: rv.Remain})
	}
	return running
}
