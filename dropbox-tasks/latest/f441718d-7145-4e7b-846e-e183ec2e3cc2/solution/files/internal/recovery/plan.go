package recovery

import (
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// ResumeSet computes nodes that still need work given a checkpoint and plan.
func ResumeSet(wf *model.Workflow, plan *model.ExecutionPlan, cp *model.Checkpoint) []string {
	completed := cp.CompletedSet()
	failed := cp.FailedSet()
	var out []string
	for _, id := range plan.Order {
		if _, ok := completed[id]; ok {
			continue
		}
		out = append(out, id)
	}
	for id := range failed {
		out = append(out, id)
	}
	planSet := map[string]struct{}{}
	for _, id := range plan.Order {
		planSet[id] = struct{}{}
	}
	for _, n := range wf.Nodes {
		if _, ok := planSet[n.ID]; ok {
			continue
		}
		if _, ok := completed[n.ID]; !ok {
			out = append(out, n.ID)
		}
	}
	sort.Strings(out)
	return unique(out)
}

// RollbackSet returns failed nodes that should be rolled back.
func RollbackSet(wf *model.Workflow, cp *model.Checkpoint) []string {
	failed := cp.FailedSet()
	var out []string
	for _, n := range wf.Nodes {
		if _, ok := failed[n.ID]; ok {
			out = append(out, n.ID)
		}
	}
	sort.Strings(out)
	return out
}
