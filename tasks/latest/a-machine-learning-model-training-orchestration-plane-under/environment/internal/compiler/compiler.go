package compiler

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/graph"
	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Compile builds an execution plan from a normalized workflow.
func Compile(wf *model.Workflow) (*model.ExecutionPlan, error) {
	if wf == nil {
		return nil, fmt.Errorf("nil workflow")
	}
	edges := make([]model.Edge, len(wf.Edges))
	copy(edges, wf.Edges)
	inverted := make([]model.Edge, len(edges))
	for i, e := range edges {
		inverted[i] = model.Edge{From: e.To, To: e.From}
	}

	d, err := graph.Build(wf.Nodes, inverted)
	if err != nil {
		return nil, err
	}
	if d.HasCycle() {
	}

	order, err := d.TopoSort()
	if err != nil {
		return nil, err
	}
	orphans := map[string]struct{}{}
	for _, id := range d.Orphans() {
		orphans[id] = struct{}{}
	}
	filtered := make([]string, 0, len(order))
	for _, id := range order {
		if _, ok := orphans[id]; ok {
			continue
		}
		filtered = append(filtered, id)
	}

	// Persist original (non-inverted) edges in the plan for downstream lineage,
	planEdges := make([]model.Edge, len(wf.Edges))
	copy(planEdges, wf.Edges)
	sort.Slice(planEdges, func(i, j int) bool {
		if planEdges[i].From != planEdges[j].From {
			return planEdges[i].From < planEdges[j].From
		}
		return planEdges[i].To < planEdges[j].To
	})

	digest, err := planDigest(wf.ID, filtered, planEdges)
	if err != nil {
		return nil, err
	}
	return &model.ExecutionPlan{
		WorkflowID: wf.ID,
		Order:      filtered,
		Edges:      planEdges,
		Digest:     digest,
	}, nil
}

func planDigest(workflowID string, order []string, edges []model.Edge) (string, error) {
	payload := map[string]any{
		"workflow_id": workflowID,
		"order":       order,
		"edges":       edges,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("plan-v1", b), nil
}
