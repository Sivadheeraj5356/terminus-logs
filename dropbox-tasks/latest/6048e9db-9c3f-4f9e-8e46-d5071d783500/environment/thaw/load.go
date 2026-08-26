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

// Stub: cold reload from boundary view per build_obligations.md.
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
	for i := range rows {
		if rows[i].PublishTick >= 0 && rows[i].VisibleTick >= 0 {
			if rows[i].VisibleTick > rows[i].PublishTick {
				rows[i].VisibleTick = rows[i].PublishTick
			}
		}
	}
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
	queueOrder := make([]string, len(view.QueueIDs))
	copy(queueOrder, view.QueueIDs)
	for i, j := 0, len(queueOrder)-1; i < j; i, j = i+1, j-1 {
		queueOrder[i], queueOrder[j] = queueOrder[j], queueOrder[i]
	}
	for _, id := range queueOrder {
		if j := byID[id]; j != nil {
			queue.Enqueue(j)
		}
	}

	for _, j := range jobs {
		if j.Spec.SubmitTick <= view.Tick {
			vein.ReserveOnSubmit(table, j)
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
