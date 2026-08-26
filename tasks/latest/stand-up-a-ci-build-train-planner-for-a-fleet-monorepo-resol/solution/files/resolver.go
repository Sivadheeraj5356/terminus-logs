package graph

import (
	"fmt"
	"sort"

	"github.com/fleet-ops/build-planner/packages/catalog"
)

func Resolve(modules []catalog.Module) ([]string, error) {
	index := catalog.Index(modules)
	indeg := map[string]int{}
	adj := map[string][]string{}

	for id := range index {
		indeg[id] = 0
	}

	for _, m := range modules {
		for _, dep := range m.Depends {
			if _, ok := index[dep]; !ok {
				return nil, fmt.Errorf("manifest_error: missing dependency %s", dep)
			}
			adj[dep] = append(adj[dep], m.ID)
			indeg[m.ID]++
		}
	}

	var queue []string
	for id, d := range indeg {
		if d == 0 {
			queue = append(queue, id)
		}
	}
	sort.Strings(queue)

	order := make([]string, 0, len(modules))
	for len(queue) > 0 {
		id := queue[0]
		queue = queue[1:]
		order = append(order, id)

		nextReady := make([]string, 0)
		for _, nxt := range adj[id] {
			indeg[nxt]--
			if indeg[nxt] == 0 {
				nextReady = append(nextReady, nxt)
			}
		}
		sort.Strings(nextReady)
		queue = append(queue, nextReady...)
	}

	if len(order) != len(modules) {
		return nil, fmt.Errorf("cycle_detected")
	}
	return order, nil
}
