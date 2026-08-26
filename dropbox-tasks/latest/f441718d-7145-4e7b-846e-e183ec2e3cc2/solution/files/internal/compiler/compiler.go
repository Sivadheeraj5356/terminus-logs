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

	d, err := graph.Build(wf.Nodes, edges)
	if err != nil {
		return nil, err
	}
	if d.HasSelfLoop() {
		return nil, fmt.Errorf("self-loop in workflow graph")
	}
	if d.HasCycle() {
		return nil, fmt.Errorf("cycle in workflow graph")
	}

	order, err := d.TopoSort()
	if err != nil {
		return nil, err
	}

	planEdges := make([]model.Edge, len(wf.Edges))
	copy(planEdges, wf.Edges)
	sort.Slice(planEdges, func(i, j int) bool {
		if planEdges[i].From != planEdges[j].From {
			return planEdges[i].From < planEdges[j].From
		}
		return planEdges[i].To < planEdges[j].To
	})

	digest, err := planDigest(wf.ID, order, planEdges)
	if err != nil {
		return nil, err
	}
	return &model.ExecutionPlan{
		WorkflowID: wf.ID,
		Order:      order,
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
