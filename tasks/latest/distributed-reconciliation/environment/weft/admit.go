package weft

import "dschedsim/internal/graph"

// Stub: dependency admission delay per build_obligations.md.
func WaitDelay(depCount int) int {
	if depCount == 0 {
		return 0
	}
	if depCount == 1 {
		return 1
	}
	return 2
}

// MarkNewlyReady stamps ready_tick when dependencies first become satisfiable.
func MarkNewlyReady(jobs []*graph.Job, done map[string]bool, tick int) {
	for _, j := range jobs {
		if j.ReadyTick >= 0 {
			continue
		}
		if len(j.Spec.Deps) == 0 {
			j.ReadyTick = tick
			continue
		}
		if depsSatisfied(j, done) {
			j.ReadyTick = tick + WaitDelay(len(j.Spec.Deps))
		}
	}
}

// Ready returns jobs whose dependencies are satisfied for scheduling.
func Ready(jobs []*graph.Job, done map[string]bool) []*graph.Job {
	var out []*graph.Job
	for _, j := range jobs {
		if j.StartTick >= 0 || j.Running || j.ReadyTick < 0 {
			continue
		}
		if depsSatisfied(j, done) {
			out = append(out, j)
		}
	}
	return out
}

func depsSatisfied(job *graph.Job, done map[string]bool) bool {
	for _, dep := range job.Spec.Deps {
		if !done[dep] {
			return false
		}
	}
	return true
}
