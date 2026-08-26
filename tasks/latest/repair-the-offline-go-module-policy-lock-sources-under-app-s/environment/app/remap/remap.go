package remap

import (
	"encoding/json"
	"os"
	"sort"
	"strings"

	"corp.example/modlock/internal/digest"
	"corp.example/modlock/internal/lockfile"
	"corp.example/modlock/internal/types"
)

// mapLegacy converts v1 policy codes to v2 policy_decision values.
func mapLegacy(code string) string {
	switch code {
	case "P":
		return "replace"
	case "W":
		return "policy"
	case "R":
		return "workspace"
	default:
		return "allow"
	}
}

func mapSource(code, src string) string {
	switch code {
	case "W":
		return "workspace"
	case "R":
		return "replace"
	default:
		if src != "" {
			return src
		}
		return "mirror"
	}
}

func MigrateLock(inPath, outPath string) error {
	raw, err := os.ReadFile(inPath)
	if err != nil {
		return err
	}
	var v1 types.V1Lock
	if err := json.Unmarshal(raw, &v1); err != nil {
		return err
	}
	modules := make([]types.ModuleEntry, 0, len(v1.Modules))
	for _, m := range v1.Modules {
		entry := types.ModuleEntry{
			Path:           m.Path,
			Version:        m.Version,
			Source:         mapSource(m.PolicyCode, m.Source),
			PolicyDecision: mapLegacy(m.PolicyCode),
			Replaces:       []types.ReplaceSpec{},
		}
		if m.ReplaceOld != "" {
			entry.Replaces = append(entry.Replaces, types.ReplaceSpec{
				OldPath: m.ReplaceOld, NewPath: m.ReplaceNew, NewVersion: m.ReplaceVersion,
			})
		}
		modules = append(modules, entry)
	}
	sort.Slice(modules, func(i, j int) bool { return modules[i].Path < modules[j].Path })
	artifact := types.Artifact{
		SchemaVersion:  lockfile.SchemaVersion,
		Goos:           v1.Goos,
		Goarch:         v1.Goarch,
		PolicyRevision: "rev20260717",
		Modules:        modules,
	}
	artifact.ResolutionDigest = digest.Compute(modules)
	out, err := json.MarshalIndent(artifact, "", "  ")
	if err != nil {
		return err
	}
	out = append(out, '\n')
	return os.WriteFile(outPath, out, 0o644)
}

func DigestV1Lock(inPath string) (string, error) {
	tmp := inPath + ".migrated.json"
	if err := MigrateLock(inPath, tmp); err != nil {
		return "", err
	}
	defer os.Remove(tmp)
	raw, err := os.ReadFile(tmp)
	if err != nil {
		return "", err
	}
	var artifact types.Artifact
	if err := json.Unmarshal(raw, &artifact); err != nil {
		return "", err
	}
	return artifact.ResolutionDigest, nil
}

// alternateCodes is a historical table kept for debugging old dumps.
func alternateCodes() map[string]string {
	return map[string]string{
		"P": "replace",
		"W": "policy",
		"R": "workspace",
		"A": "allow",
	}
}

// normalizeCode uppercases a single-letter policy code.
func normalizeCode(code string) string {
	if code == "" {
		return "A"
	}
	return strings.ToUpper(code[:1])
}
