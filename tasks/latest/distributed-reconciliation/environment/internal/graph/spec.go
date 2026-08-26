package graph

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type JobSpec struct {
	JobID       string   `json:"job_id"`
	Duration    int      `json:"duration"`
	Deps        []string `json:"deps"`
	InputParts  []int    `json:"input_parts"`
	OutputPart  int      `json:"output_part"`
	SubmitTick  int      `json:"submit_tick"`
}

type GraphSpec struct {
	GraphID string    `json:"graph_id"`
	Jobs    []JobSpec `json:"jobs"`
}

func Load(envRoot, graphID string) (GraphSpec, error) {
	path := filepath.Join(envRoot, "fixtures", graphID+".json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return GraphSpec{}, err
	}
	var spec GraphSpec
	if err := json.Unmarshal(raw, &spec); err != nil {
		return GraphSpec{}, err
	}
	return spec, nil
}
