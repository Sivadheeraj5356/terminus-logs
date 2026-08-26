package pipeline

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"dschedsim/spine"
	"dschedsim/weft"
	"dschedsim/internal/app"
	"dschedsim/internal/graph"
	"dschedsim/internal/metrics"
	"dschedsim/vein"
	"dschedsim/placement"
	"dschedsim/thaw"
	"dschedsim/drift"
	"dschedsim/slate"
)

type JobView struct {
	JobID      string `json:"job_id"`
	StartTick  int    `json:"start_tick"`
	FinishTick int    `json:"finish_tick"`
	QueueWait  int    `json:"queue_wait_ticks"`
	Duration   int    `json:"duration_ticks"`
	NodeID     int    `json:"node_id"`
}

type TickSnap struct {
	Tick         int `json:"tick"`
	ReadyCount   int `json:"ready_count"`
	QueuedCount  int `json:"queued_count"`
	RunningCount int `json:"running_count"`
	IdleNodes    int `json:"idle_nodes"`
	BlockedCount int `json:"blocked_on_partition"`
}

type Summary struct {
	JobsSubmitted        int     `json:"jobs_submitted"`
	JobsCompleted        int     `json:"jobs_completed"`
	ScheduleDuration     int     `json:"schedule_duration_ticks"`
	NodeUtilization      float64 `json:"node_utilization"`
	QueueWaitP95         int     `json:"queue_wait_p95"`
	StallIndex           float64 `json:"stall_index"`
	ScheduleFingerprint  string  `json:"schedule_fingerprint"`
	TickDispatchDigest   string  `json:"tick_dispatch_digest"`
	LedgerFingerprint    string  `json:"ledger_fingerprint"`
	ResumeTickCount      int     `json:"resume_tick_count"`
}

type Report struct {
	ConfigID        string      `json:"config_id"`
	Seed            int64       `json:"seed"`
	Profile         string      `json:"profile"`
	GraphID         string      `json:"graph_id"`
	RunMode         string      `json:"run_mode"`
	BoundaryTick    int         `json:"boundary_tick"`
	TickHorizon     int         `json:"tick_horizon"`
	NodeCount       int         `json:"node_count"`
	PartitionCount  int         `json:"partition_count"`
	Flags           app.Flags   `json:"flags"`
	Jobs            []JobView   `json:"jobs"`
	Summary         Summary     `json:"summary"`
	Ticks           []TickSnap  `json:"ticks"`
	PartitionLedger []vein.Row `json:"partition_ledger"`
}

type activeJob struct {
	job    *graph.Job
	remain int
}

type simCtx struct {
	cfg     app.Config
	jobs    []*graph.Job
	byID    map[string]*graph.Job
	table   *vein.Table
	pool    *placement.Pool
	queue   *drift.Queue
	done    map[string]bool
	running []activeJob
	ticks   []TickSnap
	peakBusy int
}

func Run(envRoot string, cfg app.Config) (Report, error) {
	spec, err := graph.Load(envRoot, cfg.GraphID)
	if err != nil {
		return Report{}, err
	}
	jobs, err := graph.Materialize(spec)
	if err != nil {
		return Report{}, err
	}

	ctx := &simCtx{
		cfg:   cfg,
		jobs:  jobs,
		byID:  graph.ByID(jobs),
		table: vein.NewTable(cfg.PartitionCount, cfg.Flags.StrictDeps),
		pool:  placement.NewPool(cfg.NodeCount),
		queue: drift.NewQueue(),
		done:  make(map[string]bool),
	}

	resumeTicks := 0
	switch cfg.RunMode {
	case "checkpoint_chain":
		bounds := spine.NormalizeBoundaries(cfg.BoundaryTicks, cfg.TickHorizon)
		if len(bounds) == 0 {
			bounds = []int{cfg.BoundaryTick}
		}
		tick := 0
		for _, boundary := range bounds {
			if boundary > cfg.TickHorizon {
				boundary = cfg.TickHorizon
			}
			if boundary <= tick {
				continue
			}
			for tick < boundary {
				ctx.runTick(tick)
				tick++
			}
			view := slate.Capture(
				boundary,
				ctx.jobs,
				ctx.table,
				ctx.pool,
				ctx.queue,
				ctx.done,
				toSnapRunning(ctx.running),
			)
			ctx.running = fromRestoreRunning(
				thaw.Hydrate(
					view,
					ctx.jobs,
					ctx.byID,
					ctx.table,
					ctx.pool,
					ctx.queue,
					ctx.done,
				),
			)
			resumeTicks += cfg.TickHorizon - boundary
		}
		for tick < cfg.TickHorizon {
			ctx.runTick(tick)
			tick++
		}
	case "checkpoint_resume":
		boundary := cfg.BoundaryTick
		if boundary > cfg.TickHorizon {
			boundary = cfg.TickHorizon
		}
		for tick := 0; tick < boundary; tick++ {
			ctx.runTick(tick)
		}
		view := slate.Capture(
			boundary,
			ctx.jobs,
			ctx.table,
			ctx.pool,
			ctx.queue,
			ctx.done,
			toSnapRunning(ctx.running),
		)
		ctx.running = fromRestoreRunning(
			thaw.Hydrate(
				view,
				ctx.jobs,
				ctx.byID,
				ctx.table,
				ctx.pool,
				ctx.queue,
				ctx.done,
			),
		)
		resumeTicks = cfg.TickHorizon - boundary
		for tick := boundary; tick < cfg.TickHorizon; tick++ {
			ctx.runTick(tick)
		}
	default:
		for tick := 0; tick < cfg.TickHorizon; tick++ {
			ctx.runTick(tick)
		}
	}

	return ctx.buildReport(resumeTicks), nil
}

func toSnapRunning(running []activeJob) []slate.ActiveJob {
	out := make([]slate.ActiveJob, 0, len(running))
	for _, aj := range running {
		out = append(out, slate.ActiveJob{Job: aj.job, Remain: aj.remain})
	}
	return out
}

func fromRestoreRunning(running []thaw.ActiveJob) []activeJob {
	out := make([]activeJob, 0, len(running))
	for _, aj := range running {
		out = append(out, activeJob{job: aj.Job, remain: aj.Remain})
	}
	return out
}

func (s *simCtx) runTick(tick int) {
	for _, j := range s.jobs {
		if j.Spec.SubmitTick == tick {
			vein.ReserveOnSubmit(s.table, j)
		}
	}
	stampAndEnqueue(s.jobs, s.done, tick, s.queue)
	s.running = dispatchTick(s.cfg, tick, s.jobs, s.byID, s.queue, s.table, s.pool, s.running, s.done)
	s.running = advanceRunning(tick, s.jobs, s.byID, s.table, s.pool, s.running, s.done)

	readyN := countReady(s.jobs, s.done)
	blocked := countBlocked(s.jobs, s.table, tick)
	busy := s.pool.Running()
	if busy > s.peakBusy {
		s.peakBusy = busy
	}
	s.ticks = append(s.ticks, TickSnap{
		Tick:         tick,
		ReadyCount:   readyN,
		QueuedCount:  s.queue.Depth(),
		RunningCount: busy,
		IdleNodes:    s.cfg.NodeCount - busy,
		BlockedCount: blocked,
	})
}

func (s *simCtx) buildReport(resumeTicks int) Report {
	views := make([]JobView, 0, len(s.jobs))
	waits := make([]int, 0, len(s.jobs))
	for _, j := range s.jobs {
		node := j.Node
		if node < 0 {
			node = -1
		}
		views = append(views, JobView{
			JobID:      j.Spec.JobID,
			StartTick:  j.StartTick,
			FinishTick: j.FinishTick,
			QueueWait:  j.QueueWait,
			Duration:   j.Spec.Duration,
			NodeID:     node,
		})
		if j.QueueWait > 0 {
			waits = append(waits, j.QueueWait)
		}
	}
	sort.Slice(views, func(i, j int) bool {
		return views[i].JobID < views[j].JobID
	})

	completed, maxFinish := summarize(s.jobs)
	lastTick := s.ticks[len(s.ticks)-1]
	ledger := s.table.Ledger()

	return Report{
		ConfigID:        s.cfg.ConfigID,
		Seed:            s.cfg.Seed,
		Profile:         s.cfg.Profile,
		GraphID:         s.cfg.GraphID,
		RunMode:         s.cfg.RunMode,
		BoundaryTick:    s.cfg.BoundaryTick,
		TickHorizon:     s.cfg.TickHorizon,
		NodeCount:       s.cfg.NodeCount,
		PartitionCount:  s.cfg.PartitionCount,
		Flags:           s.cfg.Flags,
		Jobs:            views,
		PartitionLedger: ledger,
		Summary: Summary{
			JobsSubmitted:       len(s.jobs),
			JobsCompleted:       completed,
			ScheduleDuration:    maxFinish,
			NodeUtilization:     metrics.NodeUtilization(s.peakBusy, s.cfg.NodeCount),
			QueueWaitP95:        metrics.P95Wait(waits),
			StallIndex:          metrics.StallIndex(lastTick.IdleNodes, lastTick.QueuedCount),
			ScheduleFingerprint: fingerprint(views),
			TickDispatchDigest:  tickDispatchDigest(s.ticks),
			LedgerFingerprint:   ledgerFingerprint(ledger),
			ResumeTickCount:     resumeTicks,
		},
		Ticks: s.ticks,
	}
}

func fingerprint(views []JobView) string {
	var parts []string
	for _, v := range views {
		parts = append(parts, fmt.Sprintf("%s|%d|%d|%d", v.JobID, v.StartTick, v.FinishTick, v.QueueWait))
	}
	h := sha256.Sum256([]byte(strings.Join(parts, "\n")))
	return hex.EncodeToString(h[:])
}

func tickDispatchDigest(ticks []TickSnap) string {
	var parts []string
	for _, t := range ticks {
		parts = append(parts, fmt.Sprintf(
			"%d|%d|%d|%d|%d",
			t.Tick, t.RunningCount, t.ReadyCount, t.BlockedCount, t.IdleNodes,
		))
	}
	h := sha256.Sum256([]byte(strings.Join(parts, "\n")))
	return hex.EncodeToString(h[:])
}

func ledgerFingerprint(rows []vein.Row) string {
	var parts []string
	for _, r := range rows {
		parts = append(parts, fmt.Sprintf(
			"%d|%s|%d|%d",
			r.PartitionID, r.WriterJob, r.PublishTick, r.VisibleTick,
		))
	}
	h := sha256.Sum256([]byte(strings.Join(parts, "\n")))
	return hex.EncodeToString(h[:])
}

func summarize(jobs []*graph.Job) (completed, maxFinish int) {
	for _, j := range jobs {
		if j.FinishTick >= 0 {
			completed++
			if j.FinishTick > maxFinish {
				maxFinish = j.FinishTick
			}
		}
	}
	return completed, maxFinish
}

func countReady(jobs []*graph.Job, done map[string]bool) int {
	n := 0
	for _, j := range rangeReady(jobs, done) {
		if j.StartTick < 0 && !j.Running {
			n++
		}
	}
	return n
}

func rangeReady(jobs []*graph.Job, done map[string]bool) []*graph.Job {
	return weft.Ready(jobs, done)
}

func countBlocked(jobs []*graph.Job, table *vein.Table, tick int) int {
	n := 0
	for _, j := range jobs {
		if j.StartTick >= 0 || j.Running || j.ReadyTick < 0 {
			continue
		}
		if len(j.Spec.InputParts) == 0 {
			continue
		}
		if !vein.CanRead(table, j.Spec.InputParts, tick) {
			n++
		}
	}
	return n
}
