package model

import (
	"sort"
)

// NodeByID returns a node map keyed by ID.
func (wf *Workflow) NodeByID() map[string]Node {
	out := make(map[string]Node, len(wf.Nodes))
	for _, n := range wf.Nodes {
		out[n.ID] = n
	}
	return out
}

// NodeIDs returns sorted node IDs.
func (wf *Workflow) NodeIDs() []string {
	ids := make([]string, 0, len(wf.Nodes))
	for _, n := range wf.Nodes {
		ids = append(ids, n.ID)
	}
	sort.Strings(ids)
	return ids
}

// ResultByNode indexes execution results.
func (r *ExecutionRecord) ResultByNode() map[string]NodeResult {
	out := make(map[string]NodeResult, len(r.Results))
	for _, nr := range r.Results {
		out[nr.NodeID] = nr
	}
	return out
}

// OK reports whether all node results succeeded.
func (r *ExecutionRecord) OK() bool {
	for _, nr := range r.Results {
		if nr.Status != "ok" {
			return false
		}
	}
	return len(r.Results) > 0
}

// CompletedSet returns completed node IDs from a checkpoint.
func (c *Checkpoint) CompletedSet() map[string]struct{} {
	out := make(map[string]struct{}, len(c.Completed))
	for _, id := range c.Completed {
		out[id] = struct{}{}
	}
	return out
}

// FailedSet returns failed node IDs.
func (c *Checkpoint) FailedSet() map[string]struct{} {
	out := make(map[string]struct{}, len(c.Failed))
	for _, id := range c.Failed {
		out[id] = struct{}{}
	}
	return out
}

// Healthy reports whether verification succeeded.
func (v *VerificationReport) Healthy() bool {
	return v.LineageOK && v.GraphOK && v.CheckpointOK && v.ReplayOK && v.HashOK && len(v.Issues) == 0
}

// CloneMetadata copies a string map.
func CloneMetadata(m map[string]string) map[string]string {
	out := make(map[string]string, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

// SortedEdges returns edges sorted by from,to.
func SortedEdges(edges []Edge) []Edge {
	out := append([]Edge{}, edges...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].From != out[j].From {
			return out[i].From < out[j].From
		}
		return out[i].To < out[j].To
	})
	return out
}
