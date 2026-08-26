package slate

import (
	"dschedsim/drift"
	"dschedsim/internal/graph"
	"dschedsim/placement"
	"dschedsim/vein"
)

type RunningView struct {
	JobID  string `json:"job_id"`
	Remain int    `json:"remain_ticks"`
}

type JobView struct {
	JobID      string `json:"job_id"`
	ReadyTick  int    `json:"ready_tick"`
	StartTick  int    `json:"start_tick"`
	FinishTick int    `json:"finish_tick"`
	QueueWait  int    `json:"queue_wait_ticks"`
	Running    bool   `json:"running"`
	Queued     bool   `json:"queued"`
	Node       int    `json:"node_id"`
}

type View struct {
	Tick      int           `json:"tick"`
	Done      []string      `json:"done_job_ids"`
	LeaseRows []vein.Row    `json:"lease_rows"`
	QueueIDs  []string      `json:"queue_job_ids"`
	PoolBusy  []bool        `json:"pool_busy"`
	Running   []RunningView `json:"running"`
	Jobs      []JobView     `json:"job_views"`
}

type ActiveJob struct {
	Job    *graph.Job
	Remain int
}

// Stub: boundary capture for cold reload per build_obligations.md.
func Capture(
	tick int,
	jobs []*graph.Job,
	table *vein.Table,
	pool *placement.Pool,
	queue *drift.Queue,
	done map[string]bool,
	running []ActiveJob,
) View {
	doneIDs := make([]string, 0, len(done))
	for id := range done {
		doneIDs = append(doneIDs, id)
	}

	queueIDs := queue.JobIDs()
	for i, j := 0, len(queueIDs)-1; i < j; i, j = i+1, j-1 {
		queueIDs[i], queueIDs[j] = queueIDs[j], queueIDs[i]
	}

	busy := make([]bool, len(pool.Nodes()))
	copy(busy, pool.Nodes())

	runViews := make([]RunningView, 0, len(running))
	for _, aj := range running {
		runViews = append(runViews, RunningView{
			JobID:  aj.Job.Spec.JobID,
			Remain: aj.Remain,
		})
	}

	jobViews := make([]JobView, 0, len(jobs))
	for _, j := range jobs {
		node := j.Node
		if node < 0 {
			node = -1
		}
		jobViews = append(jobViews, JobView{
			JobID:      j.Spec.JobID,
			ReadyTick:  j.ReadyTick,
			StartTick:  j.StartTick,
			FinishTick: j.FinishTick,
			QueueWait:  j.QueueWait,
			Running:    j.Running,
			Queued:     j.Queued,
			Node:       node,
		})
	}

	return View{
		Tick:      tick,
		Done:      doneIDs,
		LeaseRows: table.Ledger(),
		QueueIDs:  queueIDs,
		PoolBusy:  busy,
		Running:   runViews,
		Jobs:      jobViews,
	}
}
