package decyclose

import "sort"

type Edge struct {
	From string
	To   string
}

func DetectCycle(ids []string, edges []Edge) (bool, []string) {
	adj := map[string][]string{}
	for _, id := range ids {
		adj[id] = nil
	}
	for _, e := range edges {
		adj[e.From] = append(adj[e.From], e.To)
	}
	for id := range adj {
		sort.Strings(adj[id])
	}
	const (
		white = 0
		gray  = 1
		black = 2
	)
	color := map[string]int{}
	parent := map[string]string{}
	var cycle []string
	var dfs func(u string) bool
	dfs = func(u string) bool {
		color[u] = gray
		for _, v := range adj[u] {
			if color[v] == white {
				parent[v] = u
				if dfs(v) {
					return true
				}
			} else if color[v] == gray {
				path := []string{v}
				cur := u
				for cur != v && cur != "" {
					path = append(path, cur)
					cur = parent[cur]
				}
				path = append(path, v)
				for i, j := 0, len(path)-1; i < j; i, j = i+1, j-1 {
					path[i], path[j] = path[j], path[i]
				}
				if len(path) > 1 && path[0] == path[len(path)-1] {
					path = path[:len(path)-1]
				}
				cycle = canonicalizeCycle(path)
				return true
			}
		}
		color[u] = black
		return false
	}
	ordered := append([]string(nil), ids...)
	sort.Strings(ordered)
	for _, id := range ordered {
		if color[id] == white {
			if dfs(id) {
				return true, cycle
			}
		}
	}
	return false, nil
}

func canonicalizeCycle(nodes []string) []string {
	if len(nodes) == 0 {
		return nil
	}
	minIdx := 0
	for i := 1; i < len(nodes); i++ {
		if nodes[i] < nodes[minIdx] {
			minIdx = i
		}
	}
	out := append([]string(nil), nodes[minIdx:]...)
	out = append(out, nodes[:minIdx]...)
	return out
}

func TopoOrder(ids []string, edges []Edge) []string {
	indeg := map[string]int{}
	adj := map[string][]string{}
	for _, id := range ids {
		indeg[id] = 0
		adj[id] = nil
	}
	for _, e := range edges {
		adj[e.From] = append(adj[e.From], e.To)
		indeg[e.To]++
	}
	for id := range adj {
		sort.Strings(adj[id])
	}
	ready := []string{}
	for _, id := range ids {
		if indeg[id] == 0 {
			ready = append(ready, id)
		}
	}
	sort.Strings(ready)
	order := []string{}
	for len(ready) > 0 {
		u := ready[0]
		ready = ready[1:]
		order = append(order, u)
		for _, v := range adj[u] {
			indeg[v]--
			if indeg[v] == 0 {
				ready = append(ready, v)
				sort.Strings(ready)
			}
		}
	}
	if len(order) != len(ids) {
		return []string{}
	}
	return order
}
