package dag

import (
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/graph"
	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// Validate ensures the compiled plan is consistent with the workflow node set.
func Validate(wf *model.Workflow, plan *model.ExecutionPlan) error {
	d, err := graph.Build(wf.Nodes, plan.Edges)
	if err != nil {
		return err
	}
	if d.HasSelfLoop() {
		return dagError("dag: self-loop present")
	}
	if d.HasCycle() {
		return dagError("dag: cycle present")
	}
	seen := map[string]struct{}{}
	for _, id := range plan.Order {
		seen[id] = struct{}{}
	}
	for _, n := range wf.Nodes {
		if _, ok := seen[n.ID]; !ok {
			return dagError("dag: missing node in plan order: " + n.ID)
		}
	}
	return nil
}

type dagError string

func (e dagError) Error() string { return string(e) }

// LineageParents returns sorted parents of nodeID according to plan edges.
func LineageParents(plan *model.ExecutionPlan, nodeID string) []string {
	var parents []string
	for _, e := range plan.Edges {
		if e.To == nodeID {
			parents = append(parents, e.From)
		}
	}
	sort.Strings(parents)
	return parents
}

// LineageChildren returns sorted children of nodeID according to plan edges.
func LineageChildren(plan *model.ExecutionPlan, nodeID string) []string {
	var children []string
	for _, e := range plan.Edges {
		if e.From == nodeID {
			children = append(children, e.To)
		}
	}
	sort.Strings(children)
	return children
}
