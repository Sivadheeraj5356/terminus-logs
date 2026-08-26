package model

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func ReadJSON(path string, out any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, out)
}

func WriteJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

func LoadTree(path string) (Tree, error) {
	var t Tree
	return t, ReadJSON(path, &t)
}

func LoadWorkload(path string) (Workload, error) {
	var w Workload
	return w, ReadJSON(path, &w)
}

func LoadPolicy(path string) (Policy, []RawClause, error) {
	var p Policy
	if err := ReadJSON(path, &p); err != nil {
		return Policy{}, nil, err
	}
	base := filepath.Dir(path)
	var all []RawClause
	for _, tier := range p.Tiers {
		var chunk []RawClause
		fp := filepath.Join(base, tier.File)
		if err := ReadJSON(fp, &chunk); err != nil {
			return Policy{}, nil, fmt.Errorf("tier %d: %w", tier.ID, err)
		}
		all = append(all, chunk...)
	}
	return p, all, nil
}

func LoadManifest(path string) (map[string]ManifestEntry, error) {
	var m map[string]ManifestEntry
	return m, ReadJSON(path, &m)
}

// EmitJobs writes a line-oriented job file for the worker.
func EmitJobs(w Workload, path string) error {
	var b strings.Builder
	for _, j := range w.Jobs {
		fmt.Fprintf(&b, "JOB %s\n", j.Name)
		for _, s := range j.Steps {
			if s.Op == "read" {
				fmt.Fprintf(&b, "READ %s\n", s.Path)
			}
		}
		b.WriteString("END\n")
	}
	return os.WriteFile(path, []byte(b.String()), 0o644)
}
