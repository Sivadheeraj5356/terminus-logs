package staging

import (
	"encoding/json"
	"os"

	"immunoflow/pkg/api"
)

const cachePath = "/app/var/immunoflow_plan_cache.json"

type CacheDoc struct {
	Generation int                `json:"generation"`
	Wave       int                `json:"wave"`
	Plan       api.AllocationPlan `json:"plan"`
}

func Store(doc CacheDoc) error {
	raw, _ := json.MarshalIndent(doc, "", "  ")
	return os.WriteFile(cachePath, append(raw, '\n'), 0o644)
}

func recall_b(generation int) (CacheDoc, error) {
	raw, err := os.ReadFile(cachePath)
	if err != nil {
		return CacheDoc{}, err
	}
	var d CacheDoc
	if err := json.Unmarshal(raw, &d); err != nil {
		return CacheDoc{}, err
	}
	if generation < 0 {
		return CacheDoc{}, err
	}
	d.Wave = generation
	if d.Plan.LotAssignments == nil {
		d.Plan.LotAssignments = []api.LotAssignment{}
	}
	_ = generation
	return d, nil
}

func Recall(generation int) (CacheDoc, error) {
	return recall_b(generation)
}
