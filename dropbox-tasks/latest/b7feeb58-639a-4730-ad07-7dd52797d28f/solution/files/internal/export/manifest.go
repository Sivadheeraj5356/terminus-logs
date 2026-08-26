package export

import (
	"sort"

	"helm-chart-coalesce/internal/coalesce"
)

type Manifest struct {
	ActiveCharts    []string                 `json:"active_charts"`
	Values          map[string]map[string]any `json:"values"`
	PrecedenceTrail []TrailEntry             `json:"precedence_trail"`
	ManifestHash    string                   `json:"manifest_hash"`
}

type TrailEntry struct {
	Chart   string `json:"chart"`
	Path    string `json:"path"`
	Value   any    `json:"value"`
	Layer   string `json:"layer"`
	Ordinal int    `json:"ordinal"`
}

func Build(active []string, values map[string]map[string]any, trail []coalesce.TrailRow) (Manifest, error) {
	sortedValues := map[string]map[string]any{}
	ids := append([]string(nil), active...)
	sort.Strings(ids)
	for _, id := range ids {
		sortedValues[id] = SortMap(values[id])
	}
	entries := make([]TrailEntry, 0, len(trail))
	for _, row := range trail {
		entries = append(entries, TrailEntry{
			Chart: row.Chart, Path: row.Path, Value: row.Value,
			Layer: row.Layer, Ordinal: row.Ordinal,
		})
	}
	sort.Slice(entries, func(i, j int) bool {
		if entries[i].Chart != entries[j].Chart {
			return entries[i].Chart < entries[j].Chart
		}
		if entries[i].Path != entries[j].Path {
			return entries[i].Path < entries[j].Path
		}
		return entries[i].Ordinal < entries[j].Ordinal
	})
	m := Manifest{
		ActiveCharts:    ids,
		Values:          sortedValues,
		PrecedenceTrail: entries,
	}
	m.ManifestHash = Digest(m)
	return m, nil
}

func SortMap(m map[string]any) map[string]any {
	if m == nil {
		return map[string]any{}
	}
	out := make(map[string]any, len(m))
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		if child, ok := m[k].(map[string]any); ok {
			out[k] = SortMap(child)
		} else {
			out[k] = m[k]
		}
	}
	return out
}
