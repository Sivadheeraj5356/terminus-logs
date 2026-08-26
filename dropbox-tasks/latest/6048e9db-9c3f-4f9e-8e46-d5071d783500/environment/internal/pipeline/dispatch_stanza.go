package pipeline

import (
	"sort"

	"dschedsim/weft"
	"dschedsim/internal/app"
	"dschedsim/internal/graph"
	"dschedsim/vein"
	"dschedsim/placement"
	"dschedsim/drift"
)

func stampAndEnqueue(jobs []*graph.Job, done map[string]bool, tick int, queue *drift.Queue) {
	weft.MarkNewlyReady(jobs, done, tick)
	ready := weft.Ready(jobs, done)
	sort.Slice(ready, func(i, j int) bool {
		return ready[i].Spec.JobID < ready[j].Spec.JobID
	})
	for _, j := range ready {
		if j.StartTick >= 0 || j.Running || j.Queued {
			continue
		}
		j.Queued = true
		queue.Enqueue(j)
	}
}

func dispatchTick(
	cfg app.Config,
	tick int,
	jobs []*graph.Job,
	byID map[string]*graph.Job,
	queue *drift.Queue,
	table *vein.Table,
	pool *placement.Pool,
	running []activeJob,
	done map[string]bool,
) []activeJob {
	cap := drift.MaxDispatch(pool.Free())
	started := 0
	for started < cap && pool.Free() > 0 {
		next := queue.Pop()
		if next == nil {
			break
		}
		if next.ReadyTick > tick {
			queue.Enqueue(next)
			break
		}
		if len(next.Spec.InputParts) > 0 && !vein.CanRead(table, next.Spec.InputParts, tick) {
			queue.Enqueue(next)
			break
		}
		node, ok := pool.Stage()
		if !ok {
			queue.Enqueue(next)
			break
		}
		next.Node = node
		next.StartTick = tick
		next.Running = true
		next.Queued = false
		if next.ReadyTick >= 0 {
			next.QueueWait = tick - next.ReadyTick
		}
		_ = byID
		_ = done
		running = append(running, activeJob{job: next, remain: next.Spec.Duration})
		started++
	}
	return running
}

func advanceRunning(
	tick int,
	jobs []*graph.Job,
	byID map[string]*graph.Job,
	table *vein.Table,
	pool *placement.Pool,
	running []activeJob,
	done map[string]bool,
) []activeJob {
	var still []activeJob
	for _, aj := range running {
		if aj.remain <= 1 {
			aj.job.FinishTick = tick
			aj.job.Running = false
			done[aj.job.Spec.JobID] = true
			vein.Publish(table, aj.job, tick)
			vein.RetainAfterFinish(table, aj.job, jobs)
			pool.Release(aj.job.Node)
			continue
		}
		aj.remain--
		still = append(still, aj)
	}
	_ = byID
	return still
}
