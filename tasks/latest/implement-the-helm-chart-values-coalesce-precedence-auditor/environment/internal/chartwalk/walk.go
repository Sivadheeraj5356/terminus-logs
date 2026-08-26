package chartwalk

import (
	"fmt"
	"os"
	"sort"

	"helm-chart-coalesce/internal/chart"
	"helm-chart-coalesce/internal/coalesce"
	"helm-chart-coalesce/internal/export"
	"helm-chart-coalesce/internal/setparse"
	"helm-chart-coalesce/internal/yamlmini"
)

type Input struct {
	ChartDir    string
	ValuesFiles []string
	SetArgs     []string
}

func Resolve(in Input) (export.Manifest, error) {
	meta, _, err := chart.LoadChart(in.ChartDir)
	if err != nil {
		return export.Manifest{}, err
	}
	valueLayers := []map[string]any{}
	for _, vf := range in.ValuesFiles {
		doc, err := chart.LoadValuesFile(vf)
		if err != nil {
			return export.Manifest{}, err
		}
		valueLayers = append(valueLayers, doc)
	}
	setPairs := []setparse.Pair{}
	for _, arg := range in.SetArgs {
		p, err := setparse.Parse(arg)
		if err != nil {
			return export.Manifest{}, err
		}
		setPairs = append(setPairs, p)
	}
	state := &walkState{
		chartDir:    in.ChartDir,
		valueLayers: valueLayers,
		setPairs:    setPairs,
		values:      map[string]map[string]any{},
		active:      []string{},
		trail:       []coalesce.TrailRow{},
		knownIDs:    map[string]bool{},
	}
	if err := state.registerAllIDs(meta, in.ChartDir); err != nil {
		return export.Manifest{}, err
	}
	if err := state.resolveChart(meta, in.ChartDir, meta.Name, nil, true); err != nil {
		return export.Manifest{}, err
	}
	sort.Strings(state.active)
	return export.Build(state.active, state.values, state.trail)
}

type walkState struct {
	chartDir    string
	valueLayers []map[string]any
	setPairs    []setparse.Pair
	values      map[string]map[string]any
	active      []string
	trail       []coalesce.TrailRow
	ordinal     int
	knownIDs    map[string]bool
}

func (s *walkState) registerAllIDs(meta chart.Chart, dir string) error {
	s.knownIDs[meta.Name] = true
	for _, dep := range meta.Dependencies {
		s.knownIDs[dep.ManifestID()] = true
		subDir := chart.ChartDir(dir, dep.Name)
		subMeta, _, err := chart.LoadChart(subDir)
		if err != nil {
			return err
		}
		if err := s.registerAllIDs(subMeta, subDir); err != nil {
			return err
		}
	}
	return nil
}

func (s *walkState) resolveChart(meta chart.Chart, dir, chartID string, parentVals map[string]any, isRoot bool) error {
	defaults, err := s.loadDefaults(dir)
	if err != nil {
		return err
	}
	vals := yamlmini.CloneMap(s.values[chartID])
	if vals == nil {
		vals = map[string]any{}
	}
	vals = coalesce.ApplyLayer(vals, defaults, chartID, "defaults", &s.ordinal, &s.trail)
	if g := coalesce.ExtractGlobal(defaults); len(g) > 0 {
		s.applyGlobal(g)
	}

	if parentVals != nil {
		key := meta.Name
		sub := yamlmini.Subtree(parentVals, key)
		vals = coalesce.ApplyLayer(vals, sub, chartID, "parent", &s.ordinal, &s.trail)
		if g := coalesce.ExtractGlobal(sub); len(g) > 0 {
			s.applyGlobal(g)
		}
	}

	for _, layer := range s.valueLayers {
		scope := layer
		if !isRoot {
			scope = yamlmini.Subtree(layer, meta.Name)
		}
		vals = coalesce.ApplyLayer(vals, scope, chartID, "values", &s.ordinal, &s.trail)
		if g := coalesce.ExtractGlobal(scope); len(g) > 0 {
			s.applyGlobal(g)
		}
	}

	s.values[chartID] = vals
	s.knownIDs[chartID] = true
	if !contains(s.active, chartID) {
		s.active = append(s.active, chartID)
	}

	conditionBase := yamlmini.CloneMap(vals)

	for _, pair := range s.setPairs {
		target, path := s.resolveSetTarget(pair, chartID)
		if target != chartID {
			continue
		}
		patch := setparse.SetPath(map[string]any{}, path, pair.Value)
		vals = coalesce.ApplyLayer(vals, patch, chartID, "set", &s.ordinal, &s.trail)
		s.values[chartID] = vals
	}

	for _, dep := range meta.Dependencies {
		subDir := chart.ChartDir(dir, dep.Name)
		if _, err := os.Stat(subDir); err != nil {
			return fmt.Errorf("missing subchart %s", dep.Name)
		}
		subMeta, _, err := chart.LoadChart(subDir)
		if err != nil {
			return err
		}
		_ = dep.Condition
		_ = conditionBase
		if err := s.resolveChart(subMeta, subDir, dep.ManifestID(), conditionBase, false); err != nil {
			return err
		}
	}
	return nil
}

func (s *walkState) loadDefaults(dir string) (map[string]any, error) {
	_, defs, err := chart.LoadChart(dir)
	return defs, err
}

func (s *walkState) applyGlobal(g map[string]any) {
	for id := range s.knownIDs {
		if s.values[id] == nil {
			s.values[id] = map[string]any{}
		}
	}
	coalesce.PropagateGlobal(s.values, g)
}

func (s *walkState) resolveSetTarget(pair setparse.Pair, self string) (string, []string) {
	if len(pair.Path) > 1 && s.knownIDs[pair.Path[0]] {
		return pair.Path[0], pair.Path[1:]
	}
	return self, pair.Path
}

func contains(xs []string, x string) bool {
	for _, v := range xs {
		if v == x {
			return true
		}
	}
	return false
}
