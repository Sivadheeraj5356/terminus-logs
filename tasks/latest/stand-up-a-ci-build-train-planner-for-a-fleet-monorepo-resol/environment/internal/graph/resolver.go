package graph

import (
	"sort"

	"github.com/fleet-ops/build-planner/packages/catalog"
)

// Resolve returns a module build order.
// Baseline sorts alphabetically; production gate expects Kahn topo order with cycle detection.
func Resolve(modules []catalog.Module) ([]string, error) {
	ids := make([]string, len(modules))
	for i, m := range modules {
		ids[i] = m.ID
	}
	sort.Strings(ids)
	return ids, nil
}
