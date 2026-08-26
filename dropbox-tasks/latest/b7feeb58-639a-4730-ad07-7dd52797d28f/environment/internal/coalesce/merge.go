package coalesce

import "helm-chart-coalesce/internal/yamlmini"

func Merge(dst, src map[string]any) map[string]any {
	if dst == nil {
		dst = map[string]any{}
	}
	for k, v := range src {
		dst[k] = v
	}
	return dst
}

func ApplyLayer(dst map[string]any, src map[string]any, chartID, layer string, ordinal *int, trail *[]TrailRow) map[string]any {
	before := yamlmini.CloneMap(dst)
	out := Merge(dst, src)
	recordLeaves(chartID, before, out, layer, ordinal, trail)
	return out
}

func recordLeaves(chartID string, before, after map[string]any, layer string, ordinal *int, trail *[]TrailRow) {
	flatBefore := flatten(before, "")
	flatAfter := flatten(after, "")
	for path, val := range flatAfter {
		old, ok := flatBefore[path]
		if !ok || !equalJSON(old, val) {
			*ordinal++
			*trail = append(*trail, TrailRow{
				Chart:   chartID,
				Path:    path,
				Value:   val,
				Layer:   layer,
				Ordinal: *ordinal,
			})
		}
	}
}

func flatten(m map[string]any, prefix string) map[string]any {
	out := map[string]any{}
	for k, v := range m {
		path := k
		if prefix != "" {
			path = prefix + "." + k
		}
		if child, ok := v.(map[string]any); ok {
			for p, val := range flatten(child, path) {
				out[p] = val
			}
		} else {
			out[path] = v
		}
	}
	return out
}

func equalJSON(a, b any) bool {
	switch av := a.(type) {
	case map[string]any:
		bv, ok := b.(map[string]any)
		if !ok {
			return false
		}
		if len(av) != len(bv) {
			return false
		}
		for k, v := range av {
			if !equalJSON(v, bv[k]) {
				return false
			}
		}
		return true
	default:
		return a == b
	}
}

type TrailRow struct {
	Chart   string `json:"chart"`
	Path    string `json:"path"`
	Value   any    `json:"value"`
	Layer   string `json:"layer"`
	Ordinal int    `json:"ordinal"`
}
