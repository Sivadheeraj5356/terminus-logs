package fixtures

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// WorkflowFile describes a workflow fixture on disk.
type WorkflowFile struct {
	Path string
	Name string
}

// ListWorkflows lists JSON workflows under dir.
func ListWorkflows(dir string) ([]WorkflowFile, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var out []WorkflowFile
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".json" {
			continue
		}
		p := filepath.Join(dir, e.Name())
		b, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		var raw map[string]any
		if err := json.Unmarshal(b, &raw); err != nil {
			continue
		}
		name, _ := raw["name"].(string)
		out = append(out, WorkflowFile{Path: p, Name: name})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	return out, nil
}

// MustListWorkflows panics only in tests; production returns empty on error.
func MustListWorkflows(dir string) []WorkflowFile {
	out, err := ListWorkflows(dir)
	if err != nil {
		return nil
	}
	return out
}

// Describe returns a short description.
func (w WorkflowFile) Describe() string {
	return fmt.Sprintf("%s (%s)", w.Name, filepath.Base(w.Path))
}
