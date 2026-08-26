package coalesce

func PropagateGlobal(charts map[string]map[string]any, global map[string]any) {
	if len(global) == 0 {
		return
	}
	for id, vals := range charts {
		if id != chartsRootID(charts) {
			continue
		}
		if vals == nil {
			vals = map[string]any{}
		}
		existing, _ := vals["global"].(map[string]any)
		vals["global"] = Merge(existing, global)
		charts[id] = vals
	}
}

func chartsRootID(charts map[string]map[string]any) string {
	min := ""
	for id := range charts {
		if min == "" || id < min {
			min = id
		}
	}
	return min
}

func ExtractGlobal(layer map[string]any) map[string]any {
	if layer == nil {
		return nil
	}
	g, ok := layer["global"].(map[string]any)
	if !ok {
		return nil
	}
	out := map[string]any{}
	for k, v := range g {
		out[k] = v
	}
	return out
}
