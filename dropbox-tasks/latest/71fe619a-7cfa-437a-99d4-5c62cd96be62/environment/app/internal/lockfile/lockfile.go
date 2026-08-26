package lockfile

import (
	"encoding/json"
	"os"
	"sort"

	"corp.example/modlock/internal/digest"
	"corp.example/modlock/internal/types"
)

const SchemaVersion = "modpolicy/v2"

func Write(path string, goos, goarch, policyRevision string, modules []types.ModuleEntry) error {
	sorted := append([]types.ModuleEntry(nil), modules...)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Path < sorted[j].Path
	})
	for i := range sorted {
		if sorted[i].Replaces == nil {
			sorted[i].Replaces = []types.ReplaceSpec{}
		}
	}
	artifact := types.Artifact{
		SchemaVersion:  SchemaVersion,
		Goos:           goos,
		Goarch:         goarch,
		PolicyRevision: policyRevision,
		Modules:        sorted,
	}
	artifact.ResolutionDigest = digest.Compute(sorted)
	raw, err := json.MarshalIndent(artifact, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}

func Read(path string) (types.Artifact, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return types.Artifact{}, err
	}
	var artifact types.Artifact
	if err := json.Unmarshal(raw, &artifact); err != nil {
		return types.Artifact{}, err
	}
	return artifact, nil
}
