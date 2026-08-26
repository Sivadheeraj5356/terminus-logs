package graph

import (
	"sort"
)

// Levels assigns each node a topological level (longest path from roots).
func (d *DAG) Levels() map[string]int {
	order, err := d.TopoSort()
	if err != nil {
		return map[string]int{}
	}
	level := map[string]int{}
	for _, id := range order {
		maxParent := -1
		for _, p := range d.In[id] {
			if level[p] > maxParent {
				maxParent = level[p]
			}
		}
		level[id] = maxParent + 1
	}
	return level
}

// Roots returns nodes with indegree 0.
func (d *DAG) Roots() []string {
	var out []string
	for id := range d.Nodes {
		if len(d.In[id]) == 0 {
			out = append(out, id)
		}
	}
	sort.Strings(out)
	return out
}

// Leaves returns nodes with outdegree 0.
func (d *DAG) Leaves() []string {
	var out []string
	for id := range d.Nodes {
		if len(d.Out[id]) == 0 {
			out = append(out, id)
		}
	}
	sort.Strings(out)
	return out
}

// EdgeCount returns number of directed edges.
func (d *DAG) EdgeCount() int {
	n := 0
	for _, outs := range d.Out {
		n += len(outs)
	}
	return n
}

// Ancestors returns all transitive ancestors of nodeID.
func (d *DAG) Ancestors(nodeID string) []string {
	seen := map[string]struct{}{}
	var walk func(string)
	walk = func(u string) {
		for _, p := range d.In[u] {
			if _, ok := seen[p]; ok {
				continue
			}
			seen[p] = struct{}{}
			walk(p)
		}
	}
	walk(nodeID)
	out := make([]string, 0, len(seen))
	for id := range seen {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

// Descendants returns all transitive descendants of nodeID.
func (d *DAG) Descendants(nodeID string) []string {
	seen := map[string]struct{}{}
	var walk func(string)
	walk = func(u string) {
		for _, v := range d.Out[u] {
			if _, ok := seen[v]; ok {
				continue
			}
			seen[v] = struct{}{}
			walk(v)
		}
	}
	walk(nodeID)
	out := make([]string, 0, len(seen))
	for id := range seen {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}
