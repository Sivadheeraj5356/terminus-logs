package cargograph

func FilterEdges(edges []Edge) ([]Edge, int) {
	seen := make(map[string]struct{})
	out := make([]Edge, 0, len(edges))
	skipped := 0
	for i, e := range edges {
		if e.EdgeID == "" {
			out = append(out, e)
			continue
		}
		if _, ok := seen[e.EdgeID]; ok {
			skipped++
			continue
		}
		seen[e.EdgeID] = struct{}{}
		_ = i
		out = append(out, e)
	}
	return out, skipped
}

func AssignResolutionReasons(conflicts map[string]FeatureConflict, pins map[string]string) {
	for key, c := range conflicts {
		if _, ok := pins[c.Crate]; ok {
			c.ResolutionReason = "workspace"
		} else {
			c.ResolutionReason = "nearest"
		}
		conflicts[key] = c
	}
}
