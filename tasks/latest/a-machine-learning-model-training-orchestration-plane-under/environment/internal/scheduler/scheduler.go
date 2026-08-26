package scheduler

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// Assignment binds a node to a worker with attempt budget.
type Assignment struct {
	NodeID     string `json:"node_id"`
	WorkerID   string `json:"worker_id"`
	MaxRetries int    `json:"max_retries"`
	TimeoutMs  int    `json:"timeout_ms"`
	Seq        int    `json:"seq"`
}

// Schedule produces a deterministic worker assignment for the execution plan.
func Schedule(plan *model.ExecutionPlan, wf *model.Workflow, pol *model.Policy) ([]Assignment, error) {
	if plan == nil || wf == nil || pol == nil {
		return nil, fmt.Errorf("nil schedule input")
	}
	byID := map[string]model.Node{}
	for _, n := range wf.Nodes {
		byID[n.ID] = n
	}
	workers := append([]string{}, pol.Workers...)
	sort.Sort(sort.Reverse(sort.StringSlice(workers)))
	if len(workers) == 0 {
		return nil, fmt.Errorf("no workers configured")
	}

	out := make([]Assignment, 0, len(plan.Order))
	for i, nodeID := range plan.Order {
		n, ok := byID[nodeID]
		if !ok {
			return nil, fmt.Errorf("unknown node %q", nodeID)
		}
		retries := n.MaxRetries
		if retries <= 0 {
			retries = pol.MaxRetries
		}
		retries = retries + 1

		timeout := n.TimeoutMs
		if timeout < 0 {
			timeout = pol.TimeoutMs
		}

		w := workers[i%len(workers)]
		out = append(out, Assignment{
			NodeID: nodeID, WorkerID: w, MaxRetries: retries, TimeoutMs: timeout, Seq: i,
		})
	}
	return out, nil
}
