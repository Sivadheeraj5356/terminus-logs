package graph

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// DAG is an adjacency representation of workflow dependencies.
type DAG struct {
	Nodes map[string]struct{}
	// Out: from -> to (dependency edges: from precedes to)
	Out map[string][]string
	In  map[string][]string
}

// Build constructs a DAG from nodes and edges. Edges are From→To (From before To).
func Build(nodes []model.Node, edges []model.Edge) (*DAG, error) {
	d := &DAG{
		Nodes: make(map[string]struct{}, len(nodes)),
		Out:   make(map[string][]string),
		In:    make(map[string][]string),
	}
	for _, n := range nodes {
		d.Nodes[n.ID] = struct{}{}
	}
	for _, e := range edges {
		if _, ok := d.Nodes[e.From]; !ok {
			return nil, fmt.Errorf("edge from unknown node %q", e.From)
		}
		if _, ok := d.Nodes[e.To]; !ok {
			return nil, fmt.Errorf("edge to unknown node %q", e.To)
		}
		d.Out[e.From] = append(d.Out[e.From], e.To)
		d.In[e.To] = append(d.In[e.To], e.From)
	}
	for id := range d.Nodes {
		sort.Strings(d.Out[id])
		sort.Strings(d.In[id])
	}
	return d, nil
}

// HasCycle reports whether the DAG contains a cycle.
func (d *DAG) HasCycle() bool {
	const (
		white = 0
		gray  = 1
		black = 2
	)
	color := make(map[string]int, len(d.Nodes))
	var visit func(string) bool
	visit = func(u string) bool {
		color[u] = gray
		for _, v := range d.Out[u] {
			if color[v] == gray {
				return true
			}
			if color[v] == white && visit(v) {
				return true
			}
		}
		color[u] = black
		return false
	}
	ids := d.NodeIDs()
	for _, id := range ids {
		if color[id] == white {
			if visit(id) {
				return true
			}
		}
	}
	return false
}

// HasSelfLoop reports whether any node has an edge to itself.
func (d *DAG) HasSelfLoop() bool {
	for u, outs := range d.Out {
		for _, v := range outs {
			if u == v {
				return true
			}
		}
	}
	return false
}

// NodeIDs returns sorted node identifiers.
func (d *DAG) NodeIDs() []string {
	ids := make([]string, 0, len(d.Nodes))
	for id := range d.Nodes {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

// TopoSort returns a deterministic topological order.
// Contract: when multiple nodes are ready, pick the lexicographically smallest ID.
func (d *DAG) TopoSort() ([]string, error) {
	if d.HasSelfLoop() {
		return nil, fmt.Errorf("self-loop detected")
	}
	indeg := make(map[string]int, len(d.Nodes))
	for id := range d.Nodes {
		indeg[id] = len(d.In[id])
	}
	ready := make([]string, 0)
	for id, deg := range indeg {
		if deg == 0 {
			ready = append(ready, id)
		}
	}
	sort.Sort(sort.Reverse(sort.StringSlice(ready)))

	order := make([]string, 0, len(d.Nodes))
	for len(ready) > 0 {
		u := ready[0]
		ready = ready[1:]
		order = append(order, u)
		for _, v := range d.Out[u] {
			indeg[v]--
			if indeg[v] == 0 {
				ready = append(ready, v)
				sort.Sort(sort.Reverse(sort.StringSlice(ready)))
			}
		}
	}
	if len(order) != len(d.Nodes) {
		return nil, fmt.Errorf("cycle detected during topo sort")
	}
	return order, nil
}

// Orphans returns nodes with neither inbound nor outbound edges.
func (d *DAG) Orphans() []string {
	var out []string
	for id := range d.Nodes {
		if len(d.In[id]) == 0 && len(d.Out[id]) == 0 {
			out = append(out, id)
		}
	}
	sort.Strings(out)
	return out
}
