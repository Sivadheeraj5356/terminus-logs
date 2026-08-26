package coalesce

import "helm-chart-coalesce/internal/yamlmini"

func PropagateGlobal(charts map[string]map[string]any, global map[string]any) {
	if len(global) == 0 {
		return
	}
	for id, vals := range charts {
		if vals == nil {
			vals = map[string]any{}
		}
		existing, _ := vals["global"].(map[string]any)
		vals["global"] = Merge(existing, global)
		charts[id] = vals
	}
}

func ExtractGlobal(layer map[string]any) map[string]any {
	if layer == nil {
		return nil
	}
	g, ok := layer["global"].(map[string]any)
	if !ok {
		return nil
	}
	return yamlmini.CloneMap(g)
}
