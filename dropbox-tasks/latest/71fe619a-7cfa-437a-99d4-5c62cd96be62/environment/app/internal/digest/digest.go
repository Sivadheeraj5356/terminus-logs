package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"

	"corp.example/modlock/internal/types"
)

type digestModule struct {
	Path           string                `json:"path"`
	Version        string                `json:"version"`
	Source         string                `json:"source"`
	PolicyDecision string                `json:"policy_decision"`
	Replaces       []types.ReplaceSpec   `json:"replaces"`
}

func Compute(modules []types.ModuleEntry) string {
	sorted := append([]types.ModuleEntry(nil), modules...)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Path < sorted[j].Path
	})
	payload := make([]digestModule, 0, len(sorted))
	for _, m := range sorted {
		reps := m.Replaces
		if reps == nil {
			reps = []types.ReplaceSpec{}
		}
		payload = append(payload, digestModule{
			Path:           m.Path,
			Version:        m.Version,
			Source:         m.Source,
			PolicyDecision: m.PolicyDecision,
			Replaces:       reps,
		})
	}
	raw, _ := json.Marshal(payload)
	sum := sha256.Sum256(raw)
	return fmt.Sprintf("sha256:%s", hex.EncodeToString(sum[:]))
}
